"""Testit geokoodaukselle (docs/tuotekartta.md, vaihe E).

VAIHE 1: app.services.geokoodaus_cache-moduulin suorat yksikkötestit
(db_session-fixture + paikallinen FakeGeocoder, ei HTTP:tä).
VAIHE 2: reitittimien (henkilot/kuskit/lokaatiot POST+PUT,
POST /tuotannot/{id}/geokoodaa) läpi kulkevat testit HTTP-clientilla."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.main import app
from app.models import Geokoodi, Henkilo, HenkiloTyyppi, Kuski, Lokaatio, SopimusTyyppi, Tuotanto
from app.services.geocoder_client import get_geocoder_client
from app.services.geokoodaus_cache import geokoodaa_valimuistilla
from tests.conftest import FakeGeocoder


async def test_geokoodaa_valimuistilla_kysyy_vain_kerran(db_session):
    geocoder = FakeGeocoder({"Osoite 1": (60.1, 24.9)})

    tulos1 = await geokoodaa_valimuistilla(db_session, "Osoite 1", geocoder)
    tulos2 = await geokoodaa_valimuistilla(db_session, "Osoite 1", geocoder)

    assert tulos1 == (60.1, 24.9)
    assert tulos2 == (60.1, 24.9)
    assert geocoder.kutsut == ["Osoite 1"]


async def test_geokoodaa_valimuistilla_cachettaa_ei_loydy(db_session):
    geocoder = FakeGeocoder({})  # ei tunne mitään osoitetta

    tulos1 = await geokoodaa_valimuistilla(db_session, "Tuntematon osoite", geocoder)
    tulos2 = await geokoodaa_valimuistilla(db_session, "Tuntematon osoite", geocoder)

    assert tulos1 is None
    assert tulos2 is None
    assert geocoder.kutsut == ["Tuntematon osoite"]


async def test_geokoodaa_valimuistilla_ei_cacheta_poikkeusta(db_session):
    class FlakyGeocoder(FakeGeocoder):
        def __init__(self):
            super().__init__({"Osoite X": (60.2, 24.8)})
            self.kutsu_nro = 0

        async def geokoodaa(self, osoite):
            self.kutsu_nro += 1
            self.kutsut.append(osoite)
            if self.kutsu_nro == 1:
                raise RuntimeError("Nominatim ei vastaa")
            return self.tulokset.get(osoite)

    geocoder = FlakyGeocoder()

    tulos1 = await geokoodaa_valimuistilla(db_session, "Osoite X", geocoder)
    assert tulos1 is None  # poikkeus -> None, ei kaadu

    tulos2 = await geokoodaa_valimuistilla(db_session, "Osoite X", geocoder)
    assert tulos2 == (60.2, 24.8)  # ei ole jäänyt negatiiviseen välimuistiin
    assert geocoder.kutsut == ["Osoite X", "Osoite X"]


async def test_eri_kirjoitusasu_samasta_osoitteesta_osuu_samaan_valimuistiin(db_session):
    geocoder = FakeGeocoder({"Kauppakatu 5, Kuopio": (62.9, 27.6)})

    tulos1 = await geokoodaa_valimuistilla(db_session, "Kauppakatu 5, Kuopio", geocoder)
    tulos2 = await geokoodaa_valimuistilla(db_session, "  kauppakatu   5, kuopio ", geocoder)

    assert tulos1 == (62.9, 27.6)
    # Toinen kutsu osuu samaan väliimuistiriviin -> palauttaa cachetun
    # arvon vaikka geokooderi ei tuntisi kirjoitusasua "kauppakatu..."
    assert tulos2 == (62.9, 27.6)
    assert geocoder.kutsut == ["Kauppakatu 5, Kuopio"]


async def test_negatiivinen_valimuisti_vanhenee(db_session):
    vanha = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=8)
    db_session.add(Geokoodi(osoite="vanhentunut osoite", lat=None, lon=None, lahde="nominatim", haettu=vanha))
    await db_session.commit()

    geocoder = FakeGeocoder({"Vanhentunut osoite": (61.0, 25.0)})
    tulos = await geokoodaa_valimuistilla(db_session, "Vanhentunut osoite", geocoder)

    assert tulos == (61.0, 25.0)
    assert geocoder.kutsut == ["Vanhentunut osoite"]

    # Rivi päivittyi paikallaan, ei uutta riviä.
    rivit = (await db_session.execute(select(Geokoodi))).scalars().all()
    assert len(rivit) == 1
    assert rivit[0].lat == 61.0


async def test_positiivinen_valimuisti_ei_vanhene(db_session):
    vanha = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3650)
    db_session.add(
        Geokoodi(osoite="ikivanha osoite", lat=59.9, lon=30.3, lahde="nominatim", haettu=vanha)
    )
    await db_session.commit()

    geocoder = FakeGeocoder({"Ikivanha osoite": (0.0, 0.0)})
    tulos = await geokoodaa_valimuistilla(db_session, "Ikivanha osoite", geocoder)

    assert tulos == (59.9, 30.3)
    assert geocoder.kutsut == []


async def test_liian_pitka_osoite_ei_kaada(db_session):
    geocoder = FakeGeocoder()
    liian_pitka = "K" * 301

    tulos = await geokoodaa_valimuistilla(db_session, liian_pitka, geocoder)

    assert tulos is None
    assert geocoder.kutsut == []


# ---------------------------------------------------------------------------
# VAIHE 2: reitittimet (HTTP-client)
# ---------------------------------------------------------------------------


def _kayta_geocoderia(geocoder) -> None:
    """Korvaa conftest.py:n oletus-FakeGeocoderin tämän testin ajaksi
    tietyllä, dataa sisältävällä instanssilla (client-fixture siivoaa
    kaikki ylikirjoitukset testin lopussa)."""
    app.dependency_overrides[get_geocoder_client] = lambda: geocoder


async def test_henkilo_geokoodataan_tallennuksessa(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    _kayta_geocoderia(FakeGeocoder({"Testiosoite 1": (60.1, 24.9)}))

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Testiosoite 1"},
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["lat"] == 60.1
    assert data["lon"] == 24.9


async def test_henkilo_kasin_annettuja_koordinaatteja_ei_ylikirjoiteta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Testiosoite 1": (60.1, 24.9)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/henkilot",
        json={
            "tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1",
            "osoite": "Testiosoite 1", "lat": 61.0, "lon": 25.0,
        },
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["lat"] == 61.0
    assert data["lon"] == 25.0
    assert geocoder.kutsut == []


async def test_henkilo_geokoodaus_epaonnistuu_ei_esta_tallennusta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    _kayta_geocoderia(FakeGeocoder({}))

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Tuntematon"},
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["lat"] is None
    assert data["lon"] is None


async def test_henkilo_osoitteen_muutos_paivittaa_koordinaatit(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Osoite A": (60.1, 24.1), "Osoite B": (61.2, 25.2)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Osoite A"},
    )
    henkilo_id = vastaus.json()["id"]
    assert vastaus.json()["lat"] == 60.1

    vastaus = await client.put(
        f"/henkilot/{henkilo_id}",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Osoite B"},
    )
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["lat"] == 61.2
    assert data["lon"] == 25.2


async def test_put_annettu_lat_lon_voittaa_geokoodauksen(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Osoite A": (60.1, 24.1), "Osoite B": (61.2, 25.2)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Osoite A"},
    )
    henkilo_id = vastaus.json()["id"]
    kutsuja_ennen = len(geocoder.kutsut)

    vastaus = await client.put(
        f"/henkilot/{henkilo_id}",
        json={
            "tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1",
            "osoite": "Osoite B", "lat": 1.0, "lon": 2.0,
        },
    )
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["lat"] == 1.0
    assert data["lon"] == 2.0
    assert len(geocoder.kutsut) == kutsuja_ennen  # ei uutta geokoodauskutsua


async def test_put_sama_osoite_ei_kentta_mukana_sailyttaa_koordinaatit(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Osoite A": (60.1, 24.1)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Osoite A"},
    )
    henkilo_id = vastaus.json()["id"]
    kutsuja_ennen = len(geocoder.kutsut)

    vastaus = await client.put(
        f"/henkilot/{henkilo_id}",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1 paivitetty", "osoite": "Osoite A"},
    )
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["lat"] == 60.1
    assert data["lon"] == 24.1
    assert len(geocoder.kutsut) == kutsuja_ennen  # osoite ei muuttunut - ei uutta kutsua


async def test_kuski_geokoodataan_tallennuksessa(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    _kayta_geocoderia(FakeGeocoder({"Kuskin osoite": (60.3, 24.3)}))

    vastaus = await client.post(
        "/kuskit",
        json={
            "tuotanto_id": tuotanto_id, "nimi": "K1", "sopimus": "kuukausi",
            "koti_osoite": "Kuskin osoite",
        },
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["koti_lat"] == 60.3
    assert data["koti_lon"] == 24.3


async def test_kuski_kasin_annettuja_koordinaatteja_ei_ylikirjoiteta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Kuskin osoite": (60.3, 24.3)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/kuskit",
        json={
            "tuotanto_id": tuotanto_id, "nimi": "K1", "sopimus": "kuukausi",
            "koti_osoite": "Kuskin osoite", "koti_lat": 1.0, "koti_lon": 2.0,
        },
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["koti_lat"] == 1.0
    assert data["koti_lon"] == 2.0
    assert geocoder.kutsut == []


async def test_kuski_geokoodaus_epaonnistuu_ei_esta_tallennusta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    _kayta_geocoderia(FakeGeocoder({}))

    vastaus = await client.post(
        "/kuskit",
        json={"tuotanto_id": tuotanto_id, "nimi": "K1", "sopimus": "kuukausi", "koti_osoite": "Tuntematon"},
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["koti_lat"] is None
    assert data["koti_lon"] is None


async def test_lokaatio_geokoodataan_tallennuksessa(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    _kayta_geocoderia(FakeGeocoder({"Lokaation osoite": (60.4, 24.4)}))

    vastaus = await client.post(
        "/lokaatiot",
        json={"tuotanto_id": tuotanto_id, "nimi": "LOC1", "osoite": "Lokaation osoite"},
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["lat"] == 60.4
    assert data["lon"] == 24.4


async def test_lokaatio_kasin_annettuja_koordinaatteja_ei_ylikirjoiteta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Lokaation osoite": (60.4, 24.4)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/lokaatiot",
        json={
            "tuotanto_id": tuotanto_id, "nimi": "LOC1", "osoite": "Lokaation osoite",
            "lat": 1.0, "lon": 2.0,
        },
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["lat"] == 1.0
    assert data["lon"] == 2.0
    assert geocoder.kutsut == []


async def test_lokaatio_geokoodaus_epaonnistuu_ei_esta_tallennusta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    _kayta_geocoderia(FakeGeocoder({}))

    vastaus = await client.post(
        "/lokaatiot",
        json={"tuotanto_id": tuotanto_id, "nimi": "LOC1", "osoite": "Tuntematon"},
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert data["lat"] is None
    assert data["lon"] is None


async def test_sama_osoite_eri_entiteeteissa_geokoodataan_vain_kerran(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    geocoder = FakeGeocoder({"Jaettu osoite": (60.5, 24.5)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1", "osoite": "Jaettu osoite"},
    )
    assert vastaus.json()["lat"] == 60.5

    vastaus = await client.post(
        "/lokaatiot", json={"tuotanto_id": tuotanto_id, "nimi": "LOC1", "osoite": "Jaettu osoite"},
    )
    assert vastaus.json()["lat"] == 60.5

    assert geocoder.kutsut == ["Jaettu osoite"]


async def _seed_tuotanto(db_session) -> int:
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    return tuotanto.id


async def test_geokoodaa_tuotanto_taydentaa_koordinaatittomat(client, db_session):
    tuotanto_id = await _seed_tuotanto(db_session)
    db_session.add(
        Henkilo(
            tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CAST, nimi="H koordinaateilla",
            osoite="Henkilo A", lat=1.0, lon=2.0,
        )
    )
    db_session.add(
        Henkilo(tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CAST, nimi="H ilman", osoite="Henkilo B")
    )
    db_session.add(Kuski(tuotanto_id=tuotanto_id, nimi="K1", sopimus=SopimusTyyppi.KUUKAUSI, koti_osoite="Kuski C"))
    db_session.add(Lokaatio(tuotanto_id=tuotanto_id, nimi="LOC1", osoite="Lokaatio D"))
    await db_session.commit()

    geocoder = FakeGeocoder({"Henkilo B": (60.1, 24.1), "Lokaatio D": (60.2, 24.2)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["henkilot_paivitetty"] == 1
    assert data["henkilot_epaonnistui"] == 0
    assert data["kuskit_paivitetty"] == 0
    assert data["kuskit_epaonnistui"] == 1
    assert data["lokaatiot_paivitetty"] == 1
    assert data["lokaatiot_epaonnistui"] == 0
    assert data["jaljella"] == 0
    assert "Henkilo A" not in geocoder.kutsut  # jo koordinaatit -> ei edes yritetty


async def test_geokoodaa_tuotanto_rajoittaa_eraan_kokoa(client, db_session):
    tuotanto_id = await _seed_tuotanto(db_session)
    db_session.add(Henkilo(tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CAST, nimi="H", osoite="Osoite H"))
    db_session.add(Kuski(tuotanto_id=tuotanto_id, nimi="K", sopimus=SopimusTyyppi.KUUKAUSI, koti_osoite="Osoite K"))
    db_session.add(Lokaatio(tuotanto_id=tuotanto_id, nimi="L", osoite="Osoite L"))
    await db_session.commit()

    geocoder = FakeGeocoder({"Osoite H": (1.0, 1.0), "Osoite K": (2.0, 2.0), "Osoite L": (3.0, 3.0)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa", params={"raja": 2})
    assert vastaus.status_code == 200
    data = vastaus.json()
    kasitelty = (
        data["henkilot_paivitetty"] + data["henkilot_epaonnistui"]
        + data["kuskit_paivitetty"] + data["kuskit_epaonnistui"]
        + data["lokaatiot_paivitetty"] + data["lokaatiot_epaonnistui"]
    )
    assert kasitelty == 2
    assert data["jaljella"] == 1

    vastaus = await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa", params={"raja": 2})
    assert vastaus.status_code == 200
    assert vastaus.json()["jaljella"] == 0


async def test_geokoodaa_tuotanto_tuore_kielteinen_osuma_ei_syo_budjettia(client, db_session):
    tuotanto_id = await _seed_tuotanto(db_session)
    db_session.add(
        Henkilo(tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CAST, nimi="H", osoite="Kielteinen osoite")
    )
    db_session.add(Kuski(tuotanto_id=tuotanto_id, nimi="K", sopimus=SopimusTyyppi.KUUKAUSI, koti_osoite="Uusi osoite"))
    db_session.add(
        Geokoodi(osoite="kielteinen osoite", lat=None, lon=None, lahde="nominatim", haettu=datetime.now(UTC).replace(tzinfo=None))
    )
    await db_session.commit()

    geocoder = FakeGeocoder({"Uusi osoite": (5.0, 5.0)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa", params={"raja": 1})
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["kuskit_paivitetty"] == 1  # budjetti riitti, koska kielteinen ei syönyt sitä
    assert data["henkilot_paivitetty"] == 0
    assert data["henkilot_epaonnistui"] == 0
    assert data["jaljella"] == 1  # tuore kielteinen osuma - ei yritetty


async def test_geokoodaa_tuotanto_kelvoton_osoite_ei_syo_budjettia(client, db_session):
    tuotanto_id = await _seed_tuotanto(db_session)
    db_session.add(
        Henkilo(tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CAST, nimi="H", osoite="K" * 301)
    )
    db_session.add(Kuski(tuotanto_id=tuotanto_id, nimi="K", sopimus=SopimusTyyppi.KUUKAUSI, koti_osoite="Kelvollinen"))
    await db_session.commit()

    geocoder = FakeGeocoder({"Kelvollinen": (5.0, 5.0)})
    _kayta_geocoderia(geocoder)

    vastaus = await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa", params={"raja": 1})
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["kuskit_paivitetty"] == 1
    assert data["henkilot_epaonnistui"] == 1
    assert data["jaljella"] == 0  # kelvoton osoite ei ole "jäljellä" - ei koskaan uudestaan yritettävä


async def test_geokoodaa_tuotanto_404(client):
    vastaus = await client.post("/tuotannot/999/geokoodaa")
    assert vastaus.status_code == 404

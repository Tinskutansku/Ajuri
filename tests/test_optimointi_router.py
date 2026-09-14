"""Endpoint-testi POST /paivat/{paiva_id}/optimoi: SQLite-muistikanta +
FakeRouterClient (ei verkkokutsua). Varmistaa vastauksen muodon ja että
ajolista_versio/keikka-rivit tallentuvat oikein."""

from datetime import date, time

from app.main import app
from app.models import (
    Ajoneuvo,
    AjolistaVersio,
    Henkilo,
    HenkiloTyyppi,
    Keikka,
    Kuski,
    Kuvauspaiva,
    PaivaKuski,
    SopimusTyyppi,
    Tehtava,
    TehtavaTyyppi,
    Tuotanto,
)
from app.services.router_client import RouterClient, get_router_client


class FakeRouterClient(RouterClient):
    """Kiinteä 5 min / 1 km jokaisen erillisen pisteparin välillä — ei verkkokutsua."""

    async def matriisi(self, pisteet):
        n = len(pisteet)
        kestot = [[0 if i == j else 300 for j in range(n)] for i in range(n)]
        matkat = [[0.0 if i == j else 1000.0 for j in range(n)] for i in range(n)]
        return kestot, matkat


async def _seed(db_session) -> tuple[int, int]:
    tuotanto = Tuotanto(nimi="Testituotanto", tuntihinta_eur=20.0)
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    kuski_a = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski A", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.0,
    )
    kuski_b = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski B", sopimus=SopimusTyyppi.TUNTI,
        tuntihinta_eur=25.0, koti_lat=60.0, koti_lon=24.1,
    )
    db_session.add_all([kuski_a, kuski_b])
    await db_session.flush()

    auto_a = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto A", mukavuuspaikat=4)
    auto_b = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto B", mukavuuspaikat=4)
    db_session.add_all([auto_a, auto_b])
    await db_session.flush()

    db_session.add_all(
        [
            PaivaKuski(paiva_id=paiva.id, kuski_id=kuski_a.id, ajoneuvo_id=auto_a.id, tarjolla=True),
            PaivaKuski(paiva_id=paiva.id, kuski_id=kuski_b.id, ajoneuvo_id=auto_b.id, tarjolla=True),
        ]
    )

    db_session.add_all(
        [
            Tehtava(
                paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Nouto 1",
                henkiloita=1, mista_osoite="Hotelli A", mista_lat=60.01, mista_lon=24.0,
                mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
                perilla_viimeistaan=time(8, 0),
            ),
            Tehtava(
                paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Nouto 2",
                henkiloita=1, mista_osoite="Hotelli B", mista_lat=60.03, mista_lon=24.0,
                mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
                perilla_viimeistaan=time(8, 0),
            ),
        ]
    )
    await db_session.commit()
    return tuotanto.id, paiva.id


async def test_optimoi_paiva_palauttaa_version_ja_tallentaa_keikat(client, db_session):
    _, paiva_id = await _seed(db_session)

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 5, "skenaariot": False})
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()

    assert data["versio_nro"] == 1
    assert data["sijoittamatta"] == []
    assert data["skenaariot"] is None

    kaikki_keikat = [kk for kuski in data["kuskit"] for kk in kuski["keikat"]]
    assert len(kaikki_keikat) == 2
    assert {kk["nimi"] for kk in kaikki_keikat} == {"Nouto 1", "Nouto 2"}
    for kk in kaikki_keikat:
        assert kk["lukittu"] is False
        assert kk["keikka_id"] is not None


async def test_optimoi_paiva_puuttuva_paiva_on_404(client):
    vastaus = await client.post("/paivat/999/optimoi", json={})
    assert vastaus.status_code == 404


async def test_optimoi_paiva_ohittaa_passiiviset_tehtavat(client, db_session):
    """Vaihe B2: soft-deletetty (aktiivinen=False) tehtävä ei mene mukaan
    optimointiin, vaikka se olisi vielä kannassa."""
    _, paiva_id = await _seed(db_session)
    passiivinen = Tehtava(
        paiva_id=paiva_id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Passiivinen nouto",
        henkiloita=1, mista_osoite="X", mista_lat=60.05, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(8, 0), aktiivinen=False,
    )
    db_session.add(passiivinen)
    await db_session.commit()

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 5, "skenaariot": False})
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    nimet = {kk["nimi"] for kuski in data["kuskit"] for kk in kuski["keikat"]}
    assert nimet == {"Nouto 1", "Nouto 2"}
    assert "Passiivinen nouto" not in nimet


async def test_reoptimointi_toimii_kun_lukitun_keikan_tehtava_on_passivoitu(client, db_session):
    """Vaihe B2: jos päivä regeneroidaan optimoinnin välissä, aiemmin
    kuitattu keikka voi viitata sittemmin passivoituun tehtävään - tämän
    pitää silti näkyä oikein reoptimoinnin vastauksessa (ei KeyErroria)."""
    tuotanto = Tuotanto(nimi="Testituotanto", tuntihinta_eur=20.0)
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    kuski = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski A", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.0,
    )
    db_session.add(kuski)
    await db_session.flush()

    auto = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto A", mukavuuspaikat=4)
    db_session.add(auto)
    await db_session.flush()

    paiva_kuski = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=auto.id, tarjolla=True)
    db_session.add(paiva_kuski)
    await db_session.flush()

    lukittu_tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Aamun nouto",
        henkiloita=1, mista_osoite="Hotelli A", mista_lat=60.01, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(8, 0),
    )
    uusi_tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Iltapäivän nouto",
        henkiloita=1, mista_osoite="Hotelli B", mista_lat=60.03, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(14, 0),
    )
    db_session.add_all([lukittu_tehtava, uusi_tehtava])
    await db_session.flush()

    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True)
    db_session.add(versio)
    await db_session.flush()
    keikka = Keikka(
        versio_id=versio.id, tehtava_id=lukittu_tehtava.id, paiva_kuski_id=paiva_kuski.id,
        nouto_klo=time(6, 30), jatto_klo=time(6, 50), jarjestys=1, kuitattu=True,
    )
    db_session.add(keikka)
    await db_session.commit()

    # Simuloidaan että päivä generoitiin uudelleen sen jälkeen kun keikka kuitattiin
    lukittu_tehtava.aktiivinen = False
    await db_session.commit()

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(
            f"/paivat/{paiva.id}/optimoi",
            json={"aikaraja_s": 5, "skenaariot": False, "nyt": "10:00", "pohjaversio_id": versio.id},
        )
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    kaikki_keikat = [kk for kuski in data["kuskit"] for kk in kuski["keikat"]]
    nimet = {kk["nimi"] for kk in kaikki_keikat}
    assert nimet == {"Aamun nouto", "Iltapäivän nouto"}

    lukittu_vastaus = next(kk for kk in kaikki_keikat if kk["nimi"] == "Aamun nouto")
    assert lukittu_vastaus["lukittu"] is True
    assert lukittu_vastaus["nouto_klo"] == "06:30"


async def test_reoptimointi_toimii_kun_lukitun_keikan_kuski_on_passivoitu(client, db_session):
    """Vaihe F: jos kuski passivoidaan (soft delete) sen jälkeen kun hänen
    keikkansa kuitattiin, reoptimoinnin pitää silti näyttää lukittu keikka
    oikein (ei KeyErroria), eikä passivoitu kuski saa olla ehdolla uusille
    tehtäville."""
    tuotanto = Tuotanto(nimi="Testituotanto", tuntihinta_eur=20.0)
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    kuski = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski A", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.0,
    )
    db_session.add(kuski)
    await db_session.flush()

    auto = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto A", mukavuuspaikat=4)
    db_session.add(auto)
    await db_session.flush()

    paiva_kuski = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=auto.id, tarjolla=True)
    db_session.add(paiva_kuski)
    await db_session.flush()

    lukittu_tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Aamun nouto",
        henkiloita=1, mista_osoite="Hotelli A", mista_lat=60.01, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(8, 0),
    )
    db_session.add(lukittu_tehtava)
    await db_session.flush()

    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True)
    db_session.add(versio)
    await db_session.flush()
    keikka = Keikka(
        versio_id=versio.id, tehtava_id=lukittu_tehtava.id, paiva_kuski_id=paiva_kuski.id,
        nouto_klo=time(6, 30), jatto_klo=time(6, 50), jarjestys=1, kuitattu=True,
    )
    db_session.add(keikka)
    await db_session.commit()

    # Simuloidaan että kuski poistettiin (soft delete) sen jälkeen kun
    # keikka kuitattiin. Toinen, aktiivinen kuski jää tarjolle uusille
    # tehtäville.
    kuski.aktiivinen = False
    toinen_kuski = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski B", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.1,
    )
    db_session.add(toinen_kuski)
    await db_session.flush()
    toinen_auto = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto B", mukavuuspaikat=4)
    db_session.add(toinen_auto)
    await db_session.flush()
    db_session.add(
        PaivaKuski(paiva_id=paiva.id, kuski_id=toinen_kuski.id, ajoneuvo_id=toinen_auto.id, tarjolla=True)
    )
    uusi_tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Iltapäivän nouto",
        henkiloita=1, mista_osoite="Hotelli B", mista_lat=60.03, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(14, 0),
    )
    db_session.add(uusi_tehtava)
    await db_session.commit()

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(
            f"/paivat/{paiva.id}/optimoi",
            json={"aikaraja_s": 5, "skenaariot": False, "nyt": "10:00", "pohjaversio_id": versio.id},
        )
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    kaikki_keikat = [kk for kuski_ajolista in data["kuskit"] for kk in kuski_ajolista["keikat"]]
    nimet = {kk["nimi"] for kk in kaikki_keikat}
    assert nimet == {"Aamun nouto", "Iltapäivän nouto"}

    lukittu_vastaus = next(kk for kk in kaikki_keikat if kk["nimi"] == "Aamun nouto")
    assert lukittu_vastaus["lukittu"] is True
    assert lukittu_vastaus["nouto_klo"] == "06:30"

    # Passivoidun kuskin nimi näkyy silti lukitun keikan ajolistassa.
    passivoidun_ajolista = next(
        k for k in data["kuskit"] if any(kk["nimi"] == "Aamun nouto" for kk in k["keikat"])
    )
    assert passivoidun_ajolista["nimi"] == "Kuski A"

    # Uusi tehtävä menee aktiiviselle kuskille, ei passivoidulle.
    uuden_ajolista = next(
        k for k in data["kuskit"] if any(kk["nimi"] == "Iltapäivän nouto" for kk in k["keikat"])
    )
    assert uuden_ajolista["nimi"] == "Kuski B"


async def _seed_yksi_tehtava(db_session, *, pickup_bufferi_min=0, henkilo_bufferi_min=0):
    """Yksi kuski + yksi tehtävä, leveä aikaikkuna (00:00-10:00) ilman
    oletusarvoisia ikkunanreunoja, jotka söisivät bufferin vaikutuksen
    (sama tekniikka kuin tests/test_optimoija.py:n bufferitesteissä)."""
    tuotanto = Tuotanto(nimi="Testituotanto", tuntihinta_eur=20.0)
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    kuski = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski A", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.0, pickup_bufferi_min=pickup_bufferi_min,
    )
    db_session.add(kuski)
    await db_session.flush()

    auto = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto A", mukavuuspaikat=4)
    db_session.add(auto)
    await db_session.flush()

    db_session.add(PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=auto.id, tarjolla=True))

    henkilo = Henkilo(
        tuotanto_id=tuotanto.id, tyyppi=HenkiloTyyppi.CAST, nimi="Näyttelijä",
        nouto_bufferi_min=henkilo_bufferi_min,
    )
    db_session.add(henkilo)
    await db_session.flush()

    db_session.add(
        Tehtava(
            paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Nouto",
            henkilo_id=henkilo.id, henkiloita=1,
            mista_osoite="Hotelli A", mista_lat=60.01, mista_lon=24.0,
            mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
            nouto_aikaisintaan=time(0, 0), nouto_viimeistaan=time(10, 0),
            perilla_aikaisintaan=time(0, 0), perilla_viimeistaan=time(10, 0),
        )
    )
    await db_session.commit()
    return paiva.id


async def test_kuskin_pickup_bufferi_siirtaa_noutoaikaa(client, db_session):
    """Vaihe C: kuski.pickup_bufferi_min kulkee DB:stä TehtavaRow/KuskiRow:n
    kautta solverille asti. FakeRouterClient antaa aina 5 min - ilman
    bufferia nouto on siis 00:05, 20 min bufferilla 00:25."""
    paiva_id = await _seed_yksi_tehtava(db_session, pickup_bufferi_min=20)

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 5, "skenaariot": False})
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    kaikki_keikat = [kk for kuski in data["kuskit"] for kk in kuski["keikat"]]
    assert len(kaikki_keikat) == 1
    assert kaikki_keikat[0]["nouto_klo"] == "00:25"


async def test_henkilon_nouto_bufferi_siirtaa_noutoaikaa(client, db_session):
    paiva_id = await _seed_yksi_tehtava(db_session, henkilo_bufferi_min=10)

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 5, "skenaariot": False})
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    kaikki_keikat = [kk for kuski in data["kuskit"] for kk in kuski["keikat"]]
    assert len(kaikki_keikat) == 1
    assert kaikki_keikat[0]["nouto_klo"] == "00:15"

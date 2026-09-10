"""Testit roolipohjaiselle kenttäsuodatukselle (docs/tuotekartta.md,
vaihe D "Roolinäkyvyys"). Rooli luetaan X-Rooli-headerista (app/rooli.py),
EI ole turvaominaisuus - testit varmistavat vain että KUSKI-roolilta
piilotetut kentät todella puuttuvat vastauksesta (eivät vain ole null)."""

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


async def test_henkilo_kuski_ei_nae_bufferikenttia(client):
    vastaus = await client.post(
        "/tuotannot", json={"nimi": "Testituotanto"},
    )
    tuotanto_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/henkilot",
        json={
            "tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Näyttelijä 1",
            "nouto_bufferi_min": 5, "max_etuajassa_min": 20,
        },
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert "nouto_bufferi_min" in data
    assert "max_etuajassa_min" in data
    henkilo_id = data["id"]

    vastaus = await client.get(f"/henkilot/{henkilo_id}", headers={"X-Rooli": "kuski"})
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert "nouto_bufferi_min" not in data
    assert "max_etuajassa_min" not in data
    assert data["nimi"] == "Näyttelijä 1"

    for rooli in ("tuotanto", "koordi"):
        vastaus = await client.get(f"/henkilot/{henkilo_id}", headers={"X-Rooli": rooli})
        data = vastaus.json()
        assert "nouto_bufferi_min" in data
        assert "max_etuajassa_min" in data


async def test_kuski_kuski_ei_nae_tuntihintaa_eika_pickup_bufferia(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/kuskit",
        json={
            "tuotanto_id": tuotanto_id, "nimi": "Kuski 1", "sopimus": "kuukausi",
            "tuntihinta_eur": 25.0, "pickup_bufferi_min": 10,
        },
    )
    assert vastaus.status_code == 201
    data = vastaus.json()
    assert "tuntihinta_eur" in data
    assert "pickup_bufferi_min" in data
    kuski_id = data["id"]

    vastaus = await client.get(f"/kuskit/{kuski_id}", headers={"X-Rooli": "kuski"})
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert "tuntihinta_eur" not in data
    assert "pickup_bufferi_min" not in data
    assert data["nimi"] == "Kuski 1"

    for rooli in ("tuotanto", "koordi"):
        vastaus = await client.get(f"/kuskit/{kuski_id}", headers={"X-Rooli": rooli})
        data = vastaus.json()
        assert "tuntihinta_eur" in data
        assert "pickup_bufferi_min" in data


async def test_listaus_suodattaa_kuskilta(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Näyttelijä 1"},
    )
    await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Näyttelijä 2"},
    )

    vastaus = await client.get(
        "/henkilot", params={"tuotanto_id": tuotanto_id}, headers={"X-Rooli": "kuski"}
    )
    assert vastaus.status_code == 200
    rivit = vastaus.json()
    assert len(rivit) == 2
    for rivi in rivit:
        assert "nouto_bufferi_min" not in rivi
        assert "max_etuajassa_min" not in rivi


async def _seed_optimointidata(db_session) -> int:
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

    db_session.add(PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=auto.id, tarjolla=True))
    db_session.add(
        Tehtava(
            paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Nouto 1",
            henkiloita=1, mista_osoite="Hotelli A", mista_lat=60.01, mista_lon=24.0,
            mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
            perilla_viimeistaan=time(8, 0),
        )
    )
    await db_session.commit()
    return paiva.id


async def test_optimointi_kuski_ei_nae_kustannuksia_eika_skenaarioita(client, db_session):
    paiva_id = await _seed_optimointidata(db_session)

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(
            f"/paivat/{paiva_id}/optimoi",
            json={"aikaraja_s": 5, "skenaariot": True},
            headers={"X-Rooli": "kuski"},
        )
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    assert "kokonaiskustannus_eur" not in data
    assert "skenaariot" not in data
    assert len(data["kuskit"]) == 1
    for kuski in data["kuskit"]:
        assert "lisakustannus_eur" not in kuski
        assert "nimi" in kuski


async def test_optimointi_tuotanto_nakee_kaiken(client, db_session):
    paiva_id = await _seed_optimointidata(db_session)

    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(
            f"/paivat/{paiva_id}/optimoi",
            json={"aikaraja_s": 5, "skenaariot": True},
            headers={"X-Rooli": "tuotanto"},
        )
    finally:
        del app.dependency_overrides[get_router_client]

    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    assert "kokonaiskustannus_eur" in data
    assert "skenaariot" in data
    assert data["skenaariot"] is not None
    for kuski in data["kuskit"]:
        assert "lisakustannus_eur" in kuski


async def _seed_kaksi_versiota(db_session) -> tuple[int, int, int]:
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()
    v1 = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True, kokonaiskustannus_eur=100.0)
    v2 = AjolistaVersio(paiva_id=paiva.id, versio_nro=2, julkaistu=False, kokonaiskustannus_eur=90.0)
    db_session.add_all([v1, v2])
    await db_session.commit()
    return paiva.id, v1.id, v2.id


async def test_julkaise_versio_kuski_ei_nae_kokonaiskustannusta(client, db_session):
    _, _, v2_id = await _seed_kaksi_versiota(db_session)

    vastaus = await client.post(f"/versiot/{v2_id}/julkaise", headers={"X-Rooli": "kuski"})
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert "kokonaiskustannus_eur" not in data
    assert data["julkaistu"] is True

    vastaus = await client.post(f"/versiot/{v2_id}/julkaise")
    assert vastaus.status_code == 200
    assert "kokonaiskustannus_eur" in vastaus.json()


async def test_hae_versiot_kuski_ei_nae_kokonaiskustannusta(client, db_session):
    paiva_id, v1_id, v2_id = await _seed_kaksi_versiota(db_session)

    vastaus = await client.get("/versiot", params={"paiva_id": paiva_id}, headers={"X-Rooli": "kuski"})
    assert vastaus.status_code == 200
    rivit = vastaus.json()
    assert len(rivit) == 2
    for rivi in rivit:
        assert "kokonaiskustannus_eur" not in rivi

    vastaus = await client.get(f"/versiot/{v1_id}", headers={"X-Rooli": "kuski"})
    assert vastaus.status_code == 200
    assert "kokonaiskustannus_eur" not in vastaus.json()

    vastaus = await client.get(f"/versiot/{v1_id}")
    assert vastaus.status_code == 200
    assert vastaus.json()["kokonaiskustannus_eur"] == 100.0


async def test_hae_versiot_julkaistu_suodatin(client, db_session):
    paiva_id, v1_id, v2_id = await _seed_kaksi_versiota(db_session)

    vastaus = await client.get("/versiot", params={"paiva_id": paiva_id, "julkaistu": True})
    assert [v["id"] for v in vastaus.json()] == [v1_id]

    vastaus = await client.get("/versiot", params={"paiva_id": paiva_id, "julkaistu": False})
    assert [v["id"] for v in vastaus.json()] == [v2_id]

    vastaus = await client.get("/versiot", params={"paiva_id": paiva_id})
    assert {v["id"] for v in vastaus.json()} == {v1_id, v2_id}


async def test_hae_versiot_404(client):
    vastaus = await client.get("/versiot/999")
    assert vastaus.status_code == 404


async def test_hae_keikat_toimii_kuskilla(client, db_session):
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()
    kuski = Kuski(tuotanto_id=tuotanto.id, nimi="Kuski 1", sopimus=SopimusTyyppi.KUUKAUSI)
    ajoneuvo = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto 1")
    db_session.add_all([kuski, ajoneuvo])
    await db_session.flush()
    paiva_kuski = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=ajoneuvo.id)
    db_session.add(paiva_kuski)
    await db_session.flush()
    tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Nouto",
        mista_osoite="A", mihin_osoite="B",
    )
    db_session.add(tehtava)
    await db_session.flush()
    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1)
    db_session.add(versio)
    await db_session.flush()
    keikka = Keikka(
        versio_id=versio.id, tehtava_id=tehtava.id, paiva_kuski_id=paiva_kuski.id,
        nouto_klo=time(7, 0), jatto_klo=time(7, 15), jarjestys=1,
    )
    db_session.add(keikka)
    await db_session.commit()

    vastaus = await client.get("/keikat", params={"versio_id": versio.id}, headers={"X-Rooli": "kuski"})
    assert vastaus.status_code == 200
    rivit = vastaus.json()
    assert len(rivit) == 1
    assert rivit[0]["id"] == keikka.id


async def test_puuttuva_tai_virheellinen_rooli_oletuu_tuotannoksi(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]
    vastaus = await client.post(
        "/henkilot",
        json={
            "tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Näyttelijä 1",
            "nouto_bufferi_min": 5,
        },
    )
    henkilo_id = vastaus.json()["id"]

    vastaus = await client.get(f"/henkilot/{henkilo_id}")
    assert "nouto_bufferi_min" in vastaus.json()

    vastaus = await client.get(f"/henkilot/{henkilo_id}", headers={"X-Rooli": "hupsis"})
    assert vastaus.status_code == 200
    assert "nouto_bufferi_min" in vastaus.json()

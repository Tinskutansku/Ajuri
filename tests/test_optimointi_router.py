"""Endpoint-testi POST /paivat/{paiva_id}/optimoi: SQLite-muistikanta +
FakeRouterClient (ei verkkokutsua). Varmistaa vastauksen muodon ja että
ajolista_versio/keikka-rivit tallentuvat oikein."""

from datetime import date, time

from app.main import app
from app.models import (
    Ajoneuvo,
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

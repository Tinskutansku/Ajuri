"""GET /paivat/{id}/optimointi: Optimointi-välilehti muistaa tuloksen sivun
päivityksen yli (ROADMAP, Pienet). Kertoo onko päivän optimointi kesken
(paivan_lukko) ja mikä on päivän viimeisin tallennettu ajolistaversio."""

from app.main import app
from app.services.laskenta import paivan_lukko
from app.services.router_client import get_router_client
from tests.test_optimointi_router import FakeRouterClient, _seed


async def test_tila_ei_kaynnissa_eika_versioita(client, db_session):
    _, paiva_id = await _seed(db_session)
    vastaus = await client.get(f"/paivat/{paiva_id}/optimointi")
    assert vastaus.status_code == 200
    assert vastaus.json() == {"paiva_id": paiva_id, "kaynnissa": False, "viimeisin_versio_id": None}


async def test_tila_kaynnissa_kun_lukko_kiinni(client, db_session):
    _, paiva_id = await _seed(db_session)
    async with paivan_lukko(paiva_id):  # "optimointi kesken toisessa välilehdessä"
        vastaus = await client.get(f"/paivat/{paiva_id}/optimointi")
    assert vastaus.status_code == 200
    assert vastaus.json()["kaynnissa"] is True
    # lukon vapauduttua ei enää käynnissä
    vastaus = await client.get(f"/paivat/{paiva_id}/optimointi")
    assert vastaus.json()["kaynnissa"] is False


async def test_tila_kertoo_viimeisimman_version_optimoinnin_jalkeen(client, db_session):
    _, paiva_id = await _seed(db_session)
    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        ekat = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 1, "skenaariot": False})
        tokat = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 1, "skenaariot": False})
    finally:
        del app.dependency_overrides[get_router_client]
    assert ekat.status_code == 200, ekat.text
    assert tokat.status_code == 200, tokat.text

    vastaus = await client.get(f"/paivat/{paiva_id}/optimointi")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["kaynnissa"] is False
    assert data["viimeisin_versio_id"] == tokat.json()["versio_id"]
    assert data["viimeisin_versio_id"] != ekat.json()["versio_id"]


async def test_tila_404_tuntemattomalle_paivalle(client):
    vastaus = await client.get("/paivat/999999/optimointi")
    assert vastaus.status_code == 404

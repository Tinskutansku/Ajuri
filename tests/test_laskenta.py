"""Optimointi ajetaan erillisessä prosessissa, eikä se jumita muita
pyyntöjä (6.11.2026: säikeessä ajettu OR-Tools piti GIL:ää ja kevyetkin
haut kestivät yli 20 s). Saman päivän päällekkäinen optimointi -> 409."""

import asyncio
import os
import time

import pytest

from app.main import app
from app.routers import optimointi
from app.services.laskenta import aja_prosessissa, paivan_lukko
from app.services.router_client import get_router_client
from tests import apu_laskenta
from tests.test_optimointi_router import FakeRouterClient, _seed


async def test_aja_prosessissa_kayttaa_eri_prosessia():
    tyoprosessin_pid = await aja_prosessissa(apu_laskenta.oma_pid)
    assert tyoprosessin_pid != os.getpid()


@pytest.mark.parametrize(
    "korvattava, kuormittava",
    [
        ("ratkaise", apu_laskenta.kuormittava_ratkaise),
        ("analysoi_sijoittamattomat", apu_laskenta.kuormittava_analyysi),
    ],
)
async def test_optimointi_ei_jumita_muita_pyyntoja(client, db_session, monkeypatch, korvattava, kuormittava):
    """Jokainen OR-Toolsia ajava vaihe (pääratkaisu JA sijoittamattomien
    syyanalyysi) pitää ajaa työprosessissa."""
    _, paiva_id = await _seed(db_session)
    monkeypatch.setattr(optimointi, korvattava, kuormittava)
    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()

    valmis: dict[str, float] = {}
    kestot: list[float] = []

    async def optimoi():
        v = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 1, "skenaariot": False})
        valmis["optimointi"] = time.monotonic()
        return v

    async def muut_pyynnot():
        await asyncio.sleep(0.8)  # työprosessi on ehtinyt alkaa kuormittaa
        for _ in range(5):
            alku = time.monotonic()
            v = await client.get("/tuotannot")
            kestot.append(time.monotonic() - alku)
            assert v.status_code == 200
            await asyncio.sleep(0.1)
        valmis["muut"] = time.monotonic()

    try:
        optimointi_vastaus, _ = await asyncio.gather(optimoi(), muut_pyynnot())
    finally:
        del app.dependency_overrides[get_router_client]

    assert optimointi_vastaus.status_code == 200, optimointi_vastaus.text
    assert valmis["muut"] < valmis["optimointi"], valmis
    assert max(kestot) < 0.5, f"GET /tuotannot kesti optimoinnin aikana jopa {max(kestot):.2f} s"


async def test_saman_paivan_paallekkainen_optimointi_409(client, db_session):
    _, paiva_id = await _seed(db_session)
    async with paivan_lukko(paiva_id):  # "ensimmäinen optimointi kesken"
        vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 1, "skenaariot": False})
    assert vastaus.status_code == 409
    assert "jo käynnissä" in vastaus.json()["detail"]


async def test_lukko_vapautuu_virheen_jalkeen(client):
    # Puuttuva päivä -> 404 lukon sisällä; lukko ei saa jäädä kiinni.
    vastaus = await client.post("/paivat/999999/optimoi", json={"aikaraja_s": 1})
    assert vastaus.status_code == 404
    assert not paivan_lukko(999999).locked()


async def test_analyysi_kayttaa_lyhyttä_aikarajaa(client, db_session, monkeypatch):
    """Syyanalyysi saa lyhyen aikarajan (ANALYYSIN_AIKARAJA_S), ei pyynnön
    aikarajaa: muuten 10 sijoittamatonta x 5 kuskia x 8 s = minuutteja."""
    _, paiva_id = await _seed(db_session)
    monkeypatch.setattr(optimointi, "analysoi_sijoittamattomat", apu_laskenta.tallenna_analyysin_aikaraja)
    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json={"aikaraja_s": 5, "skenaariot": False})
    finally:
        del app.dependency_overrides[get_router_client]
    assert vastaus.status_code == 200, vastaus.text
    assert vastaus.json()["sijoittamatta"] == [
        {"tehtava_id": -1, "nimi": f"aikaraja={optimointi.ANALYYSIN_AIKARAJA_S}", "syy": "aikaikkuna", "selite": "testi"}
    ]

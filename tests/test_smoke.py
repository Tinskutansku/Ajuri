"""Savutesti: lisää henkilö omaan tuotantoon ja hae lista."""

from app.models import KayttajaRooli
from app.routers.tuotanto import TUOTANTOA_EI_VOI_LUODA
from tests.apu_tuotanto import oma_tuotanto_id


async def test_lisaa_henkilo_omaan_tuotantoon(client):
    tuotanto_id = await oma_tuotanto_id(client)

    vastaus = await client.post(
        "/henkilot",
        json={
            "tuotanto_id": tuotanto_id,
            "tyyppi": "cast",
            "nimi": "Testi Henkilö",
        },
    )
    assert vastaus.status_code == 201
    henkilo = vastaus.json()
    assert henkilo["nimi"] == "Testi Henkilö"

    vastaus = await client.get("/henkilot", params={"tuotanto_id": tuotanto_id})
    assert vastaus.status_code == 200
    henkilot = vastaus.json()
    assert len(henkilot) == 1
    assert henkilot[0]["id"] == henkilo["id"]


async def test_tuotantoa_ei_voi_luoda_apin_kautta(client, kirjaudu):
    """Tanjan päätös PR #25:ssä (A): luonti estetty kaikilta rooleilta,
    tuotanto luodaan komentorivillä (python -m app.luo_kayttaja --uusi-tuotanto)."""
    for otsakkeet in ({}, await kirjaudu(KayttajaRooli.KOORDI)):
        vastaus = await client.post(
            "/tuotannot", json={"nimi": "Uusi", "tuntihinta_eur": 20.0}, headers=otsakkeet
        )
        assert vastaus.status_code == 403
        assert vastaus.json()["detail"] == TUOTANTOA_EI_VOI_LUODA

    vastaus = await client.get("/tuotannot")
    assert [t["nimi"] for t in vastaus.json()] == ["Testituotanto"]

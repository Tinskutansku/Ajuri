"""L2: pyyntörajoitukset (app/rajoitukset.py).

Rajat luetaan asetuksista jokaisella pyynnöllä, joten testit käyttävät
oletusrajoja suoraan tai pienentävät niitä monkeypatchilla. Laskurit
nollataan jokaisen testin alussa (conftest.py: sovellus-fixture).
"""

import pytest
from starlette.requests import Request

from app.config import settings
from app.models import KayttajaRooli
from app.rajoitukset import LIIKAA_PYYNTOJA, asiakkaan_ip, kayttajan_avain

KIRJAUTUMINEN = {"email": "ei-ole@example.com", "salasana": "vaara-salasana"}


def _pyynto(otsakkeet: dict[str, str], client_ip: str = "10.0.0.1") -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [(k.lower().encode(), v.encode()) for k, v in otsakkeet.items()],
        "client": (client_ip, 12345),
    })


# ---------------------------------------------------------------------------
# POST /auth/kirjaudu: 5 / min / IP
# ---------------------------------------------------------------------------


async def test_kirjautuminen_kuudes_yritys_minuutissa_429(anon_client):
    for _ in range(5):
        r = await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN)
        assert r.status_code == 401

    r = await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN)

    assert r.status_code == 429
    assert r.json() == {"detail": LIIKAA_PYYNTOJA}
    assert r.headers["Retry-After"] == "60"
    # Turvaotsakkeet (L1) myös rajoitusvastauksessa.
    assert r.headers["X-Content-Type-Options"] == "nosniff"


async def test_kirjautumisraja_on_ip_kohtainen(anon_client, monkeypatch):
    """Välityspalvelimen takana jokainen asiakas-IP saa oman kiintiönsä."""
    monkeypatch.setattr(settings, "luotetut_valityspalvelimet", 1)
    monkeypatch.setattr(settings, "rajoitus_kirjautuminen", "2/minute")

    def ip(osoite):
        return {"X-Forwarded-For": osoite}

    for _ in range(2):
        assert (await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN,
                                       headers=ip("203.0.113.1"))).status_code == 401
    assert (await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN,
                                   headers=ip("203.0.113.1"))).status_code == 429
    # Toinen IP: oma kiintiö.
    assert (await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN,
                                   headers=ip("203.0.113.2"))).status_code == 401


async def test_vaarennetty_x_forwarded_for_ei_ohita_rajaa(anon_client, monkeypatch):
    """Asiakas voi kirjoittaa otsakkeen alkuun mitä tahansa, mutta
    välityspalvelimen lisäämä viimeinen arvo ratkaisee."""
    monkeypatch.setattr(settings, "luotetut_valityspalvelimet", 1)
    monkeypatch.setattr(settings, "rajoitus_kirjautuminen", "2/minute")

    tilat = []
    for i in range(3):
        r = await anon_client.post(
            "/auth/kirjaudu", json=KIRJAUTUMINEN,
            headers={"X-Forwarded-For": f"198.51.100.{i}, 203.0.113.9"},
        )
        tilat.append(r.status_code)
    assert tilat == [401, 401, 429]


async def test_ilman_luotettua_valityspalvelinta_otsaketta_ei_lueta(anon_client, monkeypatch):
    """Oletuksena (0 välityspalvelinta) X-Forwarded-For ohitetaan, joten
    sen vaihtelu ei anna uutta kiintiötä."""
    monkeypatch.setattr(settings, "rajoitus_kirjautuminen", "2/minute")

    tilat = []
    for i in range(3):
        r = await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN,
                                   headers={"X-Forwarded-For": f"198.51.100.{i}"})
        tilat.append(r.status_code)
    assert tilat == [401, 401, 429]


async def test_rajoitukset_pois_paalta(anon_client, monkeypatch):
    from app.rajoitukset import limiter

    monkeypatch.setattr(limiter, "enabled", False)
    for _ in range(7):
        assert (await anon_client.post("/auth/kirjaudu", json=KIRJAUTUMINEN)).status_code == 401


# ---------------------------------------------------------------------------
# GET /osoitteet/ehdota: 60 / min / käyttäjä
# ---------------------------------------------------------------------------


async def test_osoite_ehdotukset_61_haku_minuutissa_429(client):
    for _ in range(60):
        r = await client.get("/osoitteet/ehdota", params={"q": "Mannerheimintie"})
        assert r.status_code == 200

    r = await client.get("/osoitteet/ehdota", params={"q": "Mannerheimintie"})

    assert r.status_code == 429
    assert r.json() == {"detail": LIIKAA_PYYNTOJA}


async def test_osoite_ehdotusraja_on_kayttajakohtainen(anon_client, kirjaudu, monkeypatch):
    """Kaksi käyttäjää samasta IP-osoitteesta (esim. sama toimisto): kumpikin
    saa oman kiintiönsä."""
    monkeypatch.setattr(settings, "rajoitus_osoite_ehdotukset", "2/minute")
    eka = await kirjaudu(KayttajaRooli.TUOTANTO)
    toka = await kirjaudu(KayttajaRooli.KOORDI)
    hae = {"q": "Mannerheimintie"}

    for _ in range(2):
        assert (await anon_client.get("/osoitteet/ehdota", params=hae, headers=eka)).status_code == 200
    assert (await anon_client.get("/osoitteet/ehdota", params=hae, headers=eka)).status_code == 429
    assert (await anon_client.get("/osoitteet/ehdota", params=hae, headers=toka)).status_code == 200


async def test_kirjautumaton_saa_401_eika_kuluta_kiintiota(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "rajoitus_osoite_ehdotukset", "1/minute")
    for _ in range(3):
        r = await anon_client.get("/osoitteet/ehdota", params={"q": "Mannerheimintie"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /paivat/{id}/optimoi: 6 / min / käyttäjä
# ---------------------------------------------------------------------------


async def test_optimointi_seitseman_kutsua_minuutissa_429(client):
    """Olematon päivä (404) riittää: raja tarkistetaan ennen laskentaa,
    joten testi ei käynnistä optimoijaa."""
    for _ in range(6):
        r = await client.post("/paivat/999999/optimoi", json={})
        assert r.status_code == 404

    r = await client.post("/paivat/999999/optimoi", json={})

    assert r.status_code == 429
    assert r.json() == {"detail": LIIKAA_PYYNTOJA}


async def test_optimointiraja_ei_vaikuta_muihin_kayttajiin(anon_client, kirjaudu, monkeypatch):
    monkeypatch.setattr(settings, "rajoitus_optimointi", "1/minute")
    eka = await kirjaudu(KayttajaRooli.TUOTANTO)
    toka = await kirjaudu(KayttajaRooli.KOORDI)

    assert (await anon_client.post("/paivat/999999/optimoi", json={}, headers=eka)).status_code == 404
    assert (await anon_client.post("/paivat/999999/optimoi", json={}, headers=eka)).status_code == 429
    assert (await anon_client.post("/paivat/999999/optimoi", json={}, headers=toka)).status_code == 404


async def test_muut_reitit_eivat_ole_rajoitettuja(client):
    for _ in range(70):
        assert (await client.get("/henkilot")).status_code == 200


# ---------------------------------------------------------------------------
# Avainfunktiot
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hypyt", "otsake", "odotettu"),
    [
        (0, "1.1.1.1", "10.0.0.1"),             # ei luotettuja: yhteyden osoite
        (1, "1.1.1.1", "1.1.1.1"),
        (1, "6.6.6.6, 1.1.1.1", "1.1.1.1"),     # väärennetty alku ohitetaan
        (2, "1.1.1.1, 2.2.2.2", "1.1.1.1"),     # kaksi välityspalvelinta
        (2, "1.1.1.1", "10.0.0.1"),             # liian lyhyt ketju: yhteyden osoite
        (1, "", "10.0.0.1"),
    ],
)
def test_asiakkaan_ip(monkeypatch, hypyt, otsake, odotettu):
    monkeypatch.setattr(settings, "luotetut_valityspalvelimet", hypyt)
    otsakkeet = {"X-Forwarded-For": otsake} if otsake else {}
    assert asiakkaan_ip(_pyynto(otsakkeet)) == odotettu


async def test_kayttajan_avain(kirjaudu):
    otsakkeet = await kirjaudu(KayttajaRooli.TUOTANTO)
    assert kayttajan_avain(_pyynto(otsakkeet)).startswith("kayttaja:")
    assert kayttajan_avain(_pyynto({"Authorization": "Bearer roskaa"})) == "ip:10.0.0.1"
    assert kayttajan_avain(_pyynto({})) == "ip:10.0.0.1"

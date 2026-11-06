"""GET /osoitteet/ehdota ja PhotonEhdottaja. Ei oikeaa verkkoa:
endpoint-testit käyttävät FakeOsoiteEhdottajaa, Photon-toteutuksen
testit httpx.MockTransportia."""

import httpx
import pytest

from app.main import app
from app.services.osoite_ehdottaja import Ehdotus, PhotonEhdottaja, get_osoite_ehdottaja, muotoile_photon
from tests.conftest import FakeOsoiteEhdottaja


# --- Endpoint ---

async def test_ehdota_palauttaa_tulokset(client):
    fake = FakeOsoiteEhdottaja([
        Ehdotus("Humalistonkatu 1, 00250 Helsinki", 60.1771, 24.9198),
        Ehdotus("Humalistonkatu 1, 20100 Turku", 60.4527, 22.2611),
    ])
    app.dependency_overrides[get_osoite_ehdottaja] = lambda: fake

    vastaus = await client.get("/osoitteet/ehdota", params={"q": "  Humalistonkatu 1 "})

    assert vastaus.status_code == 200
    assert vastaus.json() == [
        {"nimi": "Humalistonkatu 1, 00250 Helsinki", "lat": 60.1771, "lon": 24.9198},
        {"nimi": "Humalistonkatu 1, 20100 Turku", "lat": 60.4527, "lon": 22.2611},
    ]
    assert fake.kutsut == [("Humalistonkatu 1", 5)]  # välilyönnit siistitty, oletusraja 5


async def test_ehdota_raja(client):
    fake = FakeOsoiteEhdottaja([Ehdotus(f"Katu {i}", 60.0, 24.0) for i in range(8)])
    app.dependency_overrides[get_osoite_ehdottaja] = lambda: fake

    vastaus = await client.get("/osoitteet/ehdota", params={"q": "Katu", "raja": 3})
    assert len(vastaus.json()) == 3

    liian_iso = await client.get("/osoitteet/ehdota", params={"q": "Katu", "raja": 50})
    assert liian_iso.status_code == 422


async def test_ehdota_ei_osumia_tyhja_lista(client):
    vastaus = await client.get("/osoitteet/ehdota", params={"q": "xyzzyqwerty"})
    assert vastaus.status_code == 200
    assert vastaus.json() == []


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "ab"}])
async def test_ehdota_puuttuva_tai_liian_lyhyt_haku_422(client, params):
    vastaus = await client.get("/osoitteet/ehdota", params=params)
    assert vastaus.status_code == 422


async def test_ehdota_palveluvirhe_503(client):
    class Kaatuva(FakeOsoiteEhdottaja):
        async def ehdota(self, q, raja=5):
            raise httpx.ConnectError("ei yhteyttä")

    app.dependency_overrides[get_osoite_ehdottaja] = lambda: Kaatuva()

    vastaus = await client.get("/osoitteet/ehdota", params={"q": "Mannerheimintie"})
    assert vastaus.status_code == 503
    assert "käsin" in vastaus.json()["detail"]


# --- Photon-toteutus ---

def _feature(lon, lat, **props):
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": props}


async def test_photon_parsii_ja_karsii_duplikaatit():
    pyynnot: list[httpx.Request] = []

    def kasittelija(request: httpx.Request) -> httpx.Response:
        pyynnot.append(request)
        return httpx.Response(200, json={"features": [
            _feature(24.9198, 60.1771, street="Humalistonkatu", housenumber="1",
                     postcode="00250", city="Helsinki", countrycode="FI", country="Suomi"),
            # sama osoite toisena OSM-kappaleena -> karsitaan
            _feature(24.9199, 60.1772, street="Humalistonkatu", housenumber="1",
                     postcode="00250", city="Helsinki", countrycode="FI", country="Suomi"),
            _feature(13.40, 52.52, name="Brandenburger Tor", street="Pariser Platz",
                     postcode="10117", city="Berlin", countrycode="DE", country="Deutschland"),
            {"type": "Feature", "geometry": None, "properties": {"name": "rikki"}},
        ]})

    ehdottaja = PhotonEhdottaja(
        base_url="https://photon.test", user_agent="Ajuri-testi", bias="60.17,24.94",
        transport=httpx.MockTransport(kasittelija),
    )
    tulokset = await ehdottaja.ehdota("Humalistonkatu 1", raja=5)

    assert tulokset == [
        Ehdotus("Humalistonkatu 1, 00250 Helsinki", 60.1771, 24.9198),
        Ehdotus("Brandenburger Tor, Pariser Platz, 10117 Berlin, Deutschland", 52.52, 13.40),
    ]
    p = pyynnot[0]
    assert p.url.host == "photon.test" and p.url.path == "/api/"
    assert p.url.params["q"] == "Humalistonkatu 1"
    assert p.url.params["lat"] == "60.17" and p.url.params["lon"] == "24.94"
    assert p.headers["User-Agent"] == "Ajuri-testi"


async def test_photon_valimuisti_ei_kutsu_uudestaan():
    kutsuja = 0

    def kasittelija(request: httpx.Request) -> httpx.Response:
        nonlocal kutsuja
        kutsuja += 1
        return httpx.Response(200, json={"features": [_feature(24.9, 60.1, name="Kamppi", city="Helsinki")]})

    ehdottaja = PhotonEhdottaja(base_url="https://photon.test", bias="", transport=httpx.MockTransport(kasittelija))
    eka = await ehdottaja.ehdota("Kamppi")
    toka = await ehdottaja.ehdota("  kamppi ")  # sama haku eri kirjainkoolla ja välilyönneillä

    assert eka == toka
    assert kutsuja == 1


async def test_photon_palveluvirhe_heittaa():
    ehdottaja = PhotonEhdottaja(
        base_url="https://photon.test", bias="",
        transport=httpx.MockTransport(lambda r: httpx.Response(500)),
    )
    with pytest.raises(httpx.HTTPError):
        await ehdottaja.ehdota("Mannerheimintie")


def test_muotoile_photon_katu_ilman_numeroa():
    assert muotoile_photon({"name": "Mannerheimintie", "street": None, "city": "Helsinki",
                            "countrycode": "FI"}) == "Mannerheimintie, Helsinki"

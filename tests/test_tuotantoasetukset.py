"""ROADMAP L1: tuotantoasetusten tarkistukset ja turvaotsakkeet.

Prod-sovellus rakennetaan testissä omilla asetuksillaan
(app.main.luo_sovellus), joten testit eivät riipu ympäristömuuttujista
eivätkä muuta muiden testien käyttämää kehityssovellusta.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import DEV_JWT_SECRET, Settings
from app.main import SISAINEN_VIRHE, TURVAOTSAKKEET, luo_sovellus

VAHVA_SALAISUUS = "p" * 48
PROD_KANTA = "postgresql+asyncpg://ajuri:Vahva-Kanta-Salasana-123@db:5432/ajuri"
FRONTTI = "https://ajuri.example"


def _prod(**ylikirjoitukset) -> Settings:
    arvot = {
        "ajuri_ymparisto": "prod",
        "jwt_secret": VAHVA_SALAISUUS,
        "database_url": PROD_KANTA,
    }
    arvot.update(ylikirjoitukset)
    return Settings(_env_file=None, **arvot)


@pytest.fixture(autouse=True)
def _ei_ymparistomuuttujia(monkeypatch):
    for nimi in ("AJURI_YMPARISTO", "JWT_SECRET", "DATABASE_URL", "CORS_ORIGINS"):
        monkeypatch.delenv(nimi, raising=False)


# ---------------------------------------------------------------------------
# Käynnistyksen tarkistukset
# ---------------------------------------------------------------------------


def test_prod_kelvollisilla_asetuksilla_kaynnistyy():
    s = _prod(cors_origins=[FRONTTI])
    assert s.on_prod and s.cors_origins == [FRONTTI]


def test_prod_lyhyt_jwt_secret_kaataa():
    with pytest.raises(ValidationError, match="JWT_SECRET on liian lyhyt"):
        _prod(jwt_secret="lyhyt-salaisuus")


def test_prod_kehityksen_oletusavain_kaataa():
    with pytest.raises(ValidationError, match="kehityksen oletusavain"):
        _prod(jwt_secret=DEV_JWT_SECRET)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://ajuri:ajuri@db:5432/ajuri",
        "postgresql+asyncpg://ajuri:AJURI@localhost:5433/ajuri",
        "postgresql+asyncpg://ajuri@db:5432/ajuri",  # ei salasanaa lainkaan
    ],
)
def test_prod_heikko_tai_puuttuva_kantasalasana_kaataa(url):
    with pytest.raises(ValidationError, match="tietokantasalasana"):
        _prod(database_url=url)


def test_prod_oletus_database_url_kaataa():
    # Koodin oletus-DATABASE_URL käyttää salasanaa "ajuri".
    with pytest.raises(ValidationError, match="tietokantasalasana"):
        Settings(_env_file=None, ajuri_ymparisto="prod", jwt_secret=VAHVA_SALAISUUS)


def test_prod_kertoo_kaikki_puutteet_kerralla():
    with pytest.raises(ValidationError) as virhe:
        _prod(jwt_secret="lyhyt", database_url="postgresql+asyncpg://ajuri:ajuri@db/ajuri")
    teksti = str(virhe.value)
    assert "JWT_SECRET on liian lyhyt" in teksti and "tietokantasalasana" in teksti


def test_prod_cors_tahti_kaataa():
    with pytest.raises(ValidationError, match="CORS_ORIGINS ei saa sisältää"):
        _prod(cors_origins=["*"])


def test_prod_ilman_cors_origins_ei_sallita_localhostia():
    assert _prod().cors_origins == []


def test_prod_cors_origins_ymparistomuuttujasta(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", f'["{FRONTTI}"]')
    assert _prod().cors_origins == [FRONTTI]


def test_dev_sallii_kehityksen_oletukset():
    s = Settings(_env_file=None, ajuri_ymparisto="dev")
    assert s.jwt_secret == DEV_JWT_SECRET
    assert "http://localhost:5173" in s.cors_origins
    assert not s.on_prod


# ---------------------------------------------------------------------------
# Prod-sovelluksen käytös
# ---------------------------------------------------------------------------


async def _asiakas(asetukset: Settings, sovellus=None) -> AsyncClient:
    sovellus = sovellus or luo_sovellus(asetukset)
    # raise_app_exceptions=False: Starlette nostaa käsittelemättömän
    # poikkeuksen vastauksen lähettämisen jälkeen uudelleen palvelimen
    # lokia varten; testissä halutaan nähdä vain asiakkaan saama vastaus.
    transport = ASGITransport(app=sovellus, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def prod_client() -> AsyncGenerator[AsyncClient, None]:
    async with await _asiakas(_prod(cors_origins=[FRONTTI])) as ac:
        yield ac


@pytest.mark.parametrize("polku", ["/docs", "/redoc", "/openapi.json"])
async def test_prodissa_dokumentaatio_pois(prod_client, polku):
    assert (await prod_client.get(polku)).status_code == 404


async def test_prodissa_juuri_ei_viittaa_dokumentaatioon(prod_client):
    data = (await prod_client.get("/")).json()
    assert data["dokumentaatio"] is None and data["terveys"] == "/health"


async def test_devissa_dokumentaatio_paalla():
    async with await _asiakas(Settings(_env_file=None, ajuri_ymparisto="dev")) as ac:
        assert (await ac.get("/openapi.json")).status_code == 200
        assert (await ac.get("/")).json()["dokumentaatio"] == "/docs"


async def test_prodissa_cors_sallii_vain_annetut_osoitteet(prod_client):
    def esitarkistus(origin: str) -> dict[str, str]:
        return {"Origin": origin, "Access-Control-Request-Method": "GET"}

    sallittu = await prod_client.options("/health", headers=esitarkistus(FRONTTI))
    assert sallittu.headers.get("access-control-allow-origin") == FRONTTI

    vieras = await prod_client.options("/health", headers=esitarkistus("http://localhost:5173"))
    assert "access-control-allow-origin" not in vieras.headers


async def test_odottamaton_virhe_ei_paljasta_tracebackia_eika_sqlaa():
    sovellus = luo_sovellus(_prod())

    @sovellus.get("/testi-kaatuu")
    async def kaatuu():
        raise RuntimeError("SELECT salasana_hash FROM kayttaja WHERE id = 1")

    async with await _asiakas(_prod(), sovellus) as ac:
        vastaus = await ac.get("/testi-kaatuu")
    assert vastaus.status_code == 500
    assert vastaus.json() == {"detail": SISAINEN_VIRHE}
    assert "SELECT" not in vastaus.text and "Traceback" not in vastaus.text


# ---------------------------------------------------------------------------
# Turvaotsakkeet (kaikissa ympäristöissä)
# ---------------------------------------------------------------------------


def _tarkista_otsakkeet(vastaus) -> None:
    for nimi, arvo in TURVAOTSAKKEET.items():
        assert vastaus.headers.get(nimi) == arvo, nimi


async def test_turvaotsakkeet_prodissa(prod_client):
    _tarkista_otsakkeet(await prod_client.get("/health"))
    _tarkista_otsakkeet(await prod_client.get("/henkilot"))  # 401
    _tarkista_otsakkeet(await prod_client.get("/ei-ole-olemassa"))  # 404


async def test_turvaotsakkeet_kehityssovelluksessa(client):
    _tarkista_otsakkeet(await client.get("/health"))
    _tarkista_otsakkeet(await client.get("/henkilot"))
    _tarkista_otsakkeet(await client.post("/henkilot", json={}))  # 422

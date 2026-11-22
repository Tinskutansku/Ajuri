"""ROADMAP M1: Render-julkaisu.

Tarkistaa, että Renderin antama tietokantaosoite kelpaa sellaisenaan ja
että render.yaml pitää kiinni asioista, joita julkaisu vaatii (prod-tila,
migraatiot ennen käynnistystä, salaisuudet eivät ole tiedostossa).
"""

import shlex
from pathlib import Path

import pytest
import yaml

from app.config import Settings

RENDER_YAML = Path(__file__).resolve().parent.parent / "render.yaml"


# ---------------------------------------------------------------------------
# DATABASE_URL:n skeema
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "annettu",
    [
        "postgresql://ajuri:Salainen-123@dpg-abc-a/ajuri",
        "postgres://ajuri:Salainen-123@dpg-abc-a/ajuri",
        "postgresql+asyncpg://ajuri:Salainen-123@dpg-abc-a/ajuri",
    ],
)
def test_postgres_osoite_muutetaan_asyncpg_muotoon(annettu):
    s = Settings(_env_file=None, database_url=annettu)
    assert s.database_url == "postgresql+asyncpg://ajuri:Salainen-123@dpg-abc-a/ajuri"


def test_muut_skeemat_ennallaan():
    url = "sqlite+aiosqlite:///:memory:"
    assert Settings(_env_file=None, database_url=url).database_url == url


def test_renderin_osoite_kelpaa_prodissa():
    """Renderin generoima vahva salasana läpäisee prod-tarkistuksen myös
    postgresql://-muodossa annettuna."""
    s = Settings(
        _env_file=None,
        ajuri_ymparisto="prod",
        jwt_secret="p" * 48,
        database_url="postgresql://ajuri:Xy7kQ2mZpL9vR4tW@dpg-abc-a/ajuri",
    )
    assert s.database_url.startswith("postgresql+asyncpg://")


# ---------------------------------------------------------------------------
# render.yaml
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def blueprint() -> dict:
    return yaml.safe_load(RENDER_YAML.read_text(encoding="utf-8"))


def _palvelu(blueprint: dict, runtime: str) -> dict:
    (palvelu,) = [p for p in blueprint["services"] if p["runtime"] == runtime]
    return palvelu


def _ymparisto(palvelu: dict) -> dict[str, dict]:
    return {m["key"]: m for m in palvelu.get("envVars", [])}


def test_kaikki_ilmaisella_tasolla(blueprint):
    assert all(k["plan"] == "free" for k in blueprint["databases"])
    assert _palvelu(blueprint, "docker")["plan"] == "free"


def test_backend_prod_tilassa_ja_kanta_blueprintista(blueprint):
    env = _ymparisto(_palvelu(blueprint, "docker"))
    assert env["AJURI_YMPARISTO"]["value"] == "prod"
    kanta = blueprint["databases"][0]["name"]
    assert env["DATABASE_URL"]["fromDatabase"] == {"name": kanta, "property": "connectionString"}


def test_salaisuudet_eivat_ole_tiedostossa(blueprint):
    """Tanja asettaa salaisuudet itse Renderin hallintapaneelissa."""
    backend = _ymparisto(_palvelu(blueprint, "docker"))
    frontti = _ymparisto(_palvelu(blueprint, "static"))
    for avain in ("JWT_SECRET", "CORS_ORIGINS"):
        assert backend[avain] == {"key": avain, "sync": False}
    assert frontti["VITE_API_BASE_URL"] == {"key": "VITE_API_BASE_URL", "sync": False}


def test_migraatiot_ajetaan_ennen_kaynnistysta(blueprint):
    komento = shlex.split(_palvelu(blueprint, "docker")["dockerCommand"])
    assert komento[:2] == ["sh", "-c"]
    vaiheet = [v.strip() for v in komento[2].split("&&")]
    assert vaiheet[0] == "alembic upgrade head"
    assert vaiheet[-1].startswith("exec uvicorn app.main:app")
    assert "${PORT:-8000}" in vaiheet[-1]


def test_terveystarkistus_osoittaa_avoimeen_reittiin(blueprint):
    assert _palvelu(blueprint, "docker")["healthCheckPath"] == "/health"


async def test_health_vastaa_ilman_kirjautumista(anon_client):
    r = await anon_client.get("/health")
    assert r.status_code == 200


def test_frontti_buildaa_viten_tuotantoversion(blueprint):
    frontti = _palvelu(blueprint, "static")
    assert "npm run build" in frontti["buildCommand"]
    assert frontti["staticPublishPath"] == "frontend/dist"

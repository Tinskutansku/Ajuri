"""GET / -tervetulovastaus ja tietokantayhteyden virheet -> 503.

Yhteysvirheet simuloidaan ilman verkkoa: joko get_db-ylikirjoituksella,
joka nostaa saman virheen kuin asyncpg yhteyden avauksessa, tai
SQLite-tiedostolla, jota ei voi avata (SQLAlchemy OperationalError).
"""

import socket
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import TIETOKANTA_EI_SAATAVILLA, app


async def test_juuri_palauttaa_tervetulovastauksen(client):
    vastaus = await client.get("/")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["nimi"] == app.title
    assert data["versio"] == app.version
    assert data["dokumentaatio"] == "/docs"
    assert data["terveys"] == "/health"


class _KaatuvaSessio:
    """Sessio, jonka jokainen kysely kaatuu annettuun virheeseen -
    sama kuin asyncpg:n käytös, kun Postgres ei ole käynnissä."""

    def __init__(self, virhe: Exception) -> None:
        self.virhe = virhe

    async def execute(self, *args, **kwargs):
        raise self.virhe

    async def scalars(self, *args, **kwargs):
        raise self.virhe

    async def scalar(self, *args, **kwargs):
        raise self.virhe

    async def get(self, *args, **kwargs):
        raise self.virhe


@pytest.fixture
def kaatuva_client():
    async def _tee(virhe: Exception) -> AsyncClient:
        async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
            yield _KaatuvaSessio(virhe)

        app.dependency_overrides[get_db] = override_get_db
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield _tee
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "virhe",
    [
        ConnectionRefusedError(111, "Connect call failed ('127.0.0.1', 5432)"),
        socket.gaierror(-2, "Name or service not known"),
        TimeoutError(),
    ],
    ids=["yhteys-evatty", "tuntematon-isanta", "aikakatkaisu"],
)
async def test_yhteysvirhe_palauttaa_503(kaatuva_client, virhe):
    async with await kaatuva_client(virhe) as ac:
        vastaus = await ac.get("/tuotannot")
    assert vastaus.status_code == 503
    assert vastaus.json() == {"detail": TIETOKANTA_EI_SAATAVILLA}
    # Ei tracebackia eikä yhteysosoitetta vastauksessa
    assert "Traceback" not in vastaus.text
    assert "127.0.0.1" not in vastaus.text


async def test_sqlalchemy_operational_error_palauttaa_503(tmp_path):
    # Tiedosto hakemistossa, jota ei ole -> sqlite3 ei saa yhteyttä ja
    # SQLAlchemy nostaa OperationalErrorin.
    polku = tmp_path / "ei_ole" / "kanta.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{polku}")
    sessiot = async_sessionmaker(eng, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with sessiot() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            vastaus = await ac.get("/tuotannot")
    finally:
        app.dependency_overrides.clear()
        await eng.dispose()

    assert vastaus.status_code == 503
    assert vastaus.json() == {"detail": TIETOKANTA_EI_SAATAVILLA}

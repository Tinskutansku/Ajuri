from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base
from app.services.geocoder_client import GeocoderClient, get_geocoder_client
from app.services.osoite_ehdottaja import Ehdotus, OsoiteEhdottaja, get_osoite_ehdottaja

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class FakeGeocoder(GeocoderClient):
    """Testien geokooderi - ei verkkoa. Kirjaa kutsutut osoitteet
    self.kutsut-listaan; palauttaa self.tulokset.get(osoite) tai None
    (= "ei löytynyt") oletuksena."""

    def __init__(self, tulokset: dict[str, tuple[float, float] | None] | None = None) -> None:
        self.tulokset = tulokset or {}
        self.kutsut: list[str] = []

    async def geokoodaa(self, osoite: str) -> tuple[float, float] | None:
        self.kutsut.append(osoite)
        return self.tulokset.get(osoite)


class FakeOsoiteEhdottaja(OsoiteEhdottaja):
    """Testien osoite-ehdottaja - ei verkkoa. Palauttaa self.tulokset
    ja kirjaa haut self.kutsut-listaan."""

    def __init__(self, tulokset: list[Ehdotus] | None = None) -> None:
        self.tulokset = tulokset or []
        self.kutsut: list[tuple[str, int]] = []

    async def ehdota(self, q: str, raja: int = 5) -> list[Ehdotus]:
        self.kutsut.append((q, raja))
        return self.tulokset[:raja]


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    eng = create_async_engine(DATABASE_URL, poolclass=StaticPool)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def client(engine: AsyncEngine) -> AsyncGenerator[AsyncClient, None]:
    test_session_local = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_session_local() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # Turvaverkko: mikään testi ei saa koskaan päätyä oikeaan
    # verkkokutsuun geokoodauksessa. Yksittäiset testit voivat
    # ylikirjoittaa tämän uudelleen omalla FakeGeocoder(tulokset=...)-
    # instanssillaan (ks. test_optimointi_router.py:n vastaava kuvio
    # get_router_client:lle).
    app.dependency_overrides[get_geocoder_client] = lambda: FakeGeocoder()
    app.dependency_overrides[get_osoite_ehdottaja] = lambda: FakeOsoiteEhdottaja()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    test_session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with test_session_local() as session:
        yield session

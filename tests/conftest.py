import itertools
from collections.abc import AsyncGenerator, Awaitable, Callable

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth import luo_token
from app.database import get_db
from app.main import app
from app.models import Base, Kayttaja, KayttajaRooli, Tuotanto
from app.rajoitukset import limiter
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
async def sovellus(engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Asettaa testikannan ja feikkipalvelut sovellukselle."""
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
    # Pyyntörajoitusten laskurit ovat prosessin muistissa: jokainen testi
    # aloittaa täysillä kiintiöillä (ROADMAP L2).
    limiter.reset()
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def anon_client(sovellus) -> AsyncGenerator[AsyncClient, None]:
    """Kirjautumaton asiakas (ei Authorization-otsaketta)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def tuotanto_id(engine: AsyncEngine) -> int:
    """Kirjautuneen testikäyttäjän oma tuotanto. Testit, jotka luovat
    dataa kantaan suoraan, käyttävät tätä (ks. tests/apu_tuotanto.py)."""
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        tuotanto = Tuotanto(nimi="Testituotanto")
        s.add(tuotanto)
        await s.commit()
        return tuotanto.id


Kirjaudu = Callable[..., Awaitable[dict[str, str]]]


@pytest_asyncio.fixture
async def kirjaudu(engine: AsyncEngine, tuotanto_id: int) -> Kirjaudu:
    """Tehdas: luo käyttäjän annetulla roolilla ja palauttaa
    Authorization-otsakkeen. Oletuksena testikäyttäjän tuotanto.

        otsakkeet = await kirjaudu(KayttajaRooli.KUSKI)
        await client.get("/henkilot", headers=otsakkeet)
    """
    laskuri = itertools.count(1)

    async def _kirjaudu(
        rooli: KayttajaRooli = KayttajaRooli.TUOTANTO,
        *,
        tuotanto_id: int = tuotanto_id,
        kuski_id: int | None = None,
    ) -> dict[str, str]:
        async with async_sessionmaker(engine, expire_on_commit=False)() as s:
            kayttaja = Kayttaja(
                tuotanto_id=tuotanto_id, email=f"testi{next(laskuri)}@ajuri.test",
                nimi=f"Testi {rooli.value}", rooli=rooli, kuski_id=kuski_id, aktiivinen=True,
            )
            s.add(kayttaja)
            await s.commit()
            return {"Authorization": f"Bearer {luo_token(kayttaja)}"}

    return _kirjaudu


@pytest_asyncio.fixture
async def client(sovellus, kirjaudu: Kirjaudu) -> AsyncGenerator[AsyncClient, None]:
    """Asiakas, joka on kirjautunut TUOTANTO-roolilla testituotantoon."""
    transport = ASGITransport(app=app)
    otsakkeet = await kirjaudu(KayttajaRooli.TUOTANTO)
    async with AsyncClient(transport=transport, base_url="http://test", headers=otsakkeet) as ac:
        yield ac


@pytest_asyncio.fixture
async def koordi_otsakkeet(kirjaudu: Kirjaudu) -> dict[str, str]:
    return await kirjaudu(KayttajaRooli.KOORDI)


@pytest_asyncio.fixture
async def kuski_otsakkeet(kirjaudu: Kirjaudu) -> dict[str, str]:
    return await kirjaudu(KayttajaRooli.KUSKI)


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    test_session_local = async_sessionmaker(engine, expire_on_commit=False)
    async with test_session_local() as session:
        yield session

import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import settings
from app.rooli import vaadi_kirjautuminen
from app.services.laskenta import sammuta_pooli
from app.routers import (
    ajoneuvo,
    auth,
    henkilo,
    keikat,
    kuski,
    kuvauspaiva,
    lokaatio,
    optimointi,
    osoitteet,
    paiva_henkilo,
    paiva_kuski,
    paiva_lokaatio,
    tehtava,
    tehtava_generointi,
    tuotanto,
    versiot,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="Ajolista API")
# Optimoinnin työprosessit suljetaan sovelluksen sammuessa (myös --reload).
app.router.on_shutdown.append(sammuta_pooli)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Kirjautuminen: /auth/kirjaudu on avoin, /auth/mina tarkistaa tokenin itse.
app.include_router(auth.router)

# Kaikki muut reitit vaativat voimassa olevan tokenin, ja KUSKI-rooli saa
# vain lukea (ROADMAP K2). Avoimia ovat lisäksi GET / ja GET /health
# alla sekä FastAPIn omat /docs ja /openapi.json.
_KIRJAUTUNEILLE = [Depends(vaadi_kirjautuminen)]
for _reititin in (
    tuotanto.router,
    henkilo.router,
    kuski.router,
    ajoneuvo.router,
    lokaatio.router,
    kuvauspaiva.router,
    paiva_lokaatio.router,
    paiva_henkilo.router,
    paiva_kuski.router,
    tehtava.router,
    tehtava_generointi.router,
    versiot.router,
    keikat.router,
    optimointi.router,
    osoitteet.router,
):
    app.include_router(_reititin, dependencies=_KIRJAUTUNEILLE)


# Tietokantayhteyden katkos -> 503 selkeällä viestillä raa'an 500-
# tracebackin sijaan. asyncpg nostaa yhteyden avauksessa raa'an
# OSErrorin (ConnectionRefusedError, socket.gaierror, TimeoutError),
# jota SQLAlchemy ei kääri; kesken yhteyden tulevat katkot SQLAlchemy
# käärii OperationalErroriksi / InterfaceErroriksi. Ulkoisten palvelujen
# (OSRM, Nominatim) httpx-virheet eivät ole OSErroreita, joten ne eivät
# päädy tänne.
TIETOKANTA_EI_SAATAVILLA = (
    "Tietokantaan ei saada yhteyttä. Tarkista, että tietokanta on käynnissä "
    "(esim. docker compose up db), ja yritä hetken päästä uudelleen."
)


async def tietokantayhteys_virhe(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Tietokantayhteyden virhe pyynnössä %s %s: %r",
        request.method,
        request.url.path,
        exc,
    )
    return JSONResponse(
        status_code=503,
        content={"detail": TIETOKANTA_EI_SAATAVILLA},
    )


for _virhetyyppi in (OSError, OperationalError, InterfaceError):
    app.add_exception_handler(_virhetyyppi, tietokantayhteys_virhe)


@app.get("/")
async def juuri():
    return {
        "nimi": app.title,
        "versio": app.version,
        "dokumentaatio": "/docs",
        "terveys": "/health",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}

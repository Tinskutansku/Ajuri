import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import settings
from app.services.laskenta import sammuta_pooli
from app.routers import (
    ajoneuvo,
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

app.include_router(tuotanto.router)
app.include_router(henkilo.router)
app.include_router(kuski.router)
app.include_router(ajoneuvo.router)
app.include_router(lokaatio.router)
app.include_router(kuvauspaiva.router)
app.include_router(paiva_lokaatio.router)
app.include_router(paiva_henkilo.router)
app.include_router(paiva_kuski.router)
app.include_router(tehtava.router)
app.include_router(tehtava_generointi.router)
app.include_router(versiot.router)
app.include_router(keikat.router)
app.include_router(optimointi.router)
app.include_router(osoitteet.router)


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

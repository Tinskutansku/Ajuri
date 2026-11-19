import logging

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import InterfaceError, OperationalError

from app.config import Settings, settings
from app.rajoitukset import liikaa_pyyntoja, limiter
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

# Selaimelle kerrottavat turvaotsakkeet jokaiseen vastaukseen (ROADMAP L1).
# API palauttaa vain JSONia, joten sitä ei tarvitse koskaan näyttää kehyksessä
# eikä viitata sen osoitteisiin muille sivustoille.
TURVAOTSAKKEET = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}

SISAINEN_VIRHE = "Palvelimella tapahtui odottamaton virhe. Yritä hetken päästä uudelleen."


class TurvaotsakkeetMiddleware:
    """Puhdas ASGI-middleware: lisää TURVAOTSAKKEET jokaisen HTTP-vastauksen
    alkuun koskematta runkoon (toimii myös virhe- ja esitarkistusvastauksille)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def lisaa_otsakkeet(viesti: Message) -> None:
            if viesti["type"] == "http.response.start":
                otsakkeet = MutableHeaders(scope=viesti)
                for nimi, arvo in TURVAOTSAKKEET.items():
                    otsakkeet.setdefault(nimi, arvo)
            await send(viesti)

        await self.app(scope, receive, lisaa_otsakkeet)


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


async def odottamaton_virhe(request: Request, exc: Exception) -> JSONResponse:
    """Käsittelemätön poikkeus -> 500 yleisellä viestillä. Traceback ja
    mahdollinen SQL menevät vain palvelimen lokiin, ei vastaukseen."""
    logger.exception("Odottamaton virhe pyynnössä %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": SISAINEN_VIRHE})


def luo_sovellus(asetukset: Settings) -> FastAPI:
    """Rakentaa sovelluksen annetuilla asetuksilla. Prodissa (ROADMAP L1)
    /docs, /redoc ja /openapi.json ovat pois päältä. Testit voivat rakentaa
    prod-sovelluksen omilla asetuksillaan."""
    dokumentaatio = {} if not asetukset.on_prod else {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    app = FastAPI(title="Ajolista API", debug=False, **dokumentaatio)
    # Optimoinnin työprosessit suljetaan sovelluksen sammuessa (myös --reload).
    app.router.on_shutdown.append(sammuta_pooli)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=asetukset.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Lisätään CORSin jälkeen, jolloin tämä on uloimpana ja otsakkeet tulevat
    # myös CORS-esitarkistusten (OPTIONS) vastauksiin.
    app.add_middleware(TurvaotsakkeetMiddleware)

    # Kirjautuminen: /auth/kirjaudu on avoin, /auth/mina tarkistaa tokenin itse.
    app.include_router(auth.router)

    # Kaikki muut reitit vaativat voimassa olevan tokenin, ja KUSKI-rooli saa
    # vain lukea (ROADMAP K2). Avoimia ovat lisäksi GET / ja GET /health
    # alla sekä kehityksessä FastAPIn omat /docs ja /openapi.json.
    kirjautuneille = [Depends(vaadi_kirjautuminen)]
    for reititin in (
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
        app.include_router(reititin, dependencies=kirjautuneille)

    # Pyyntörajoitukset (ROADMAP L2): slowapi lukee rajoittimen app.statesta.
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, liikaa_pyyntoja)

    for virhetyyppi in (OSError, OperationalError, InterfaceError):
        app.add_exception_handler(virhetyyppi, tietokantayhteys_virhe)
    app.add_exception_handler(Exception, odottamaton_virhe)

    @app.get("/")
    async def juuri():
        return {
            "nimi": app.title,
            "versio": app.version,
            # Prodissa dokumentaatio on pois päältä -> null.
            "dokumentaatio": app.docs_url,
            "terveys": "/health",
        }

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = luo_sovellus(settings)

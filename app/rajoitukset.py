"""Pyyntörajoitukset (ROADMAP L2), toteutettu slowapi-kirjastolla.

Rajoitetut reitit:

- `POST /auth/kirjaudu`: IP-osoitteen mukaan (käyttäjää ei vielä tiedetä).
  Hidastaa salasanojen arvailua.
- `GET /osoitteet/ehdota`: kirjautuneen käyttäjän mukaan. Photonin reilun
  käytön periaate: yksi käyttäjä ei saa tukkia julkista palvelua.
- `POST /paivat/{id}/optimoi`: kirjautuneen käyttäjän mukaan. Yksi kutsu
  varaa työprosessin noin minuutiksi.

Raja ylittyy -> 429 ja `Retry-After`-otsake. Rajat ovat asetuksia
(`app/config.py`, esim. `RAJOITUS_KIRJAUTUMINEN=5/minute`), ja ne luetaan
jokaisella pyynnöllä, joten testit voivat vaihtaa niitä lennossa.

Laskurit ovat prosessin muistissa. Se riittää, koska backend ajetaan
yhtenä uvicorn-prosessina (Dockerfile). Jos prosesseja tulee useampi,
jokaisella on omat laskurinsa, ja raja moninkertaistuu: silloin tarvitaan
yhteinen tallennus (esim. Redis, slowapi tukee sitä `storage_uri`:lla).

Rajoitus tarkistetaan vasta, kun reitin dependencyt (kirjautuminen) ovat
menneet läpi: kirjautumaton saa 401:n eikä kuluta kenenkään kiintiötä.
"""

from __future__ import annotations

import math

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.auth import VirheellinenToken, pura_token
from app.config import settings

LIIKAA_PYYNTOJA = "Liian monta pyyntöä lyhyessä ajassa. Odota hetki ja yritä uudelleen."


def asiakkaan_ip(request: Request) -> str:
    """Pyynnön tekijän IP-osoite.

    Oletuksena (`LUOTETUT_VALITYSPALVELIMET=0`) käytetään TCP-yhteyden
    vastapuolta. Välityspalvelimen (esim. Render) takana se on aina
    välityspalvelimen oma osoite, jolloin kaikki käyttäjät jakaisivat yhden
    kiintiön. Silloin asetetaan luotettujen välityspalvelinten määrä N, ja
    IP luetaan `X-Forwarded-For`-otsakkeesta N:nneksi oikealta.

    Vasemmanpuoleisinta arvoa ei käytetä koskaan: asiakas voi kirjoittaa
    otsakkeeseen mitä tahansa, ja välityspalvelimet vain lisäävät omat
    havaintonsa loppuun. Oikealta laskettu arvo on välityspalvelimen
    kirjoittama, joten sitä ei voi väärentää.
    """
    hypyt = settings.luotetut_valityspalvelimet
    if hypyt > 0:
        ketju = [osa.strip() for osa in request.headers.get("x-forwarded-for", "").split(",")]
        ketju = [osa for osa in ketju if osa]
        if len(ketju) >= hypyt:
            return ketju[-hypyt]
    return request.client.host if request.client else "tuntematon"


def kayttajan_avain(request: Request) -> str:
    """Kirjautuneen käyttäjän tunniste tokenista. Reitin kirjautumis-
    dependency on jo tarkistanut tokenin, joten purku onnistuu; varalla
    IP-osoite."""
    otsake = request.headers.get("authorization", "")
    tyyppi, _, token = otsake.partition(" ")
    if tyyppi.lower() == "bearer" and token:
        try:
            return f"kayttaja:{pura_token(token).kayttaja_id}"
        except VirheellinenToken:
            pass
    return f"ip:{asiakkaan_ip(request)}"


# Liukuva ikkuna: "5/minute" tarkoittaa enintään viittä pyyntöä minkä
# tahansa 60 sekunnin aikana (ei kellon minuutin vaihteessa nollautuvaa).
limiter = Limiter(
    key_func=asiakkaan_ip,
    strategy="moving-window",
    enabled=settings.rajoitukset_kaytossa,
)


def raja_kirjautuminen() -> str:
    return settings.rajoitus_kirjautuminen


def raja_osoite_ehdotukset() -> str:
    return settings.rajoitus_osoite_ehdotukset


def raja_optimointi() -> str:
    return settings.rajoitus_optimointi


async def liikaa_pyyntoja(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 suomenkielisellä viestillä. Retry-After = ikkunan pituus
    sekunteina: sen jälkeen kiintiö on varmasti vapautunut."""
    try:
        odota_s = max(1, math.ceil(exc.limit.limit.get_expiry()))
    except AttributeError:
        odota_s = 60
    return JSONResponse(
        status_code=429,
        content={"detail": LIIKAA_PYYNTOJA},
        headers={"Retry-After": str(odota_s)},
    )

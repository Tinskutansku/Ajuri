"""Kirjautunut käyttäjä ja hänen roolinsa pyynnöstä (ROADMAP K2).

Rooli luetaan `Authorization: Bearer <token>` -otsakkeen JWT-tokenista
(app/auth.py). Vanha `X-Rooli`-otsake on poistettu: sitä ei lueta enää
mistään, joten asiakas ei voi itse valita rooliaan.

Kolme dependencyä:

- `kirjautunut_kayttaja`: token -> aktiivinen käyttäjä, muuten 401.
- `nykyinen_rooli`: kirjautuneen käyttäjän rooli. Reitittimet käyttävät
  tätä kenttäsuodatukseen (`app/response_filter.py`); kutsupaikat eivät
  muuttuneet K2:ssa.
- `vaadi_kirjautuminen`: liitetään reitittimiin `main.py`:ssä. Vaatii
  tokenin kaikilta reiteiltä ja estää KUSKI-roolilta kaikki muokkaukset
  (403).

FastAPI välimuistittaa dependencyt pyynnön sisällä, joten käyttäjä
haetaan kannasta vain kerran, vaikka reitti käyttäisi useampaa näistä.
"""

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import VirheellinenToken, pura_token
from app.database import get_db
from app.models import Kayttaja, KayttajaRooli

EI_KIRJAUTUNUT = "Kirjautuminen puuttuu tai istunto on vanhentunut."
EI_OIKEUTTA_MUOKATA = "Kuski-roolilla ei voi muokata tietoja."

# Metodit, jotka eivät muuta mitään. Kaikki muut (POST, PUT, PATCH,
# DELETE) ovat muokkauksia, jotka KUSKI-roolilta on estetty.
LUKUMETODIT = frozenset({"GET", "HEAD", "OPTIONS"})

_bearer = HTTPBearer(auto_error=False)


def _ei_kirjautunut() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=EI_KIRJAUTUNUT,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def kirjautunut_kayttaja(
    tunnus: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Kayttaja:
    """Authorization: Bearer <token> -> aktiivinen käyttäjä, muuten 401."""
    if tunnus is None:
        raise _ei_kirjautunut()
    try:
        sisalto = pura_token(tunnus.credentials)
    except VirheellinenToken:
        raise _ei_kirjautunut()
    kayttaja = await db.get(Kayttaja, sisalto.kayttaja_id)
    # Passivoitu käyttäjä menettää pääsyn heti, vaikka token olisi voimassa.
    if kayttaja is None or not kayttaja.aktiivinen:
        raise _ei_kirjautunut()
    # Tuotanto ja rooli tokenista. Jos käyttäjän rooli tai tuotanto on
    # vaihdettu kannassa tokenin myöntämisen jälkeen, vanha token ei enää
    # kelpaa: käyttäjä kirjautuu uudelleen ja saa ajantasaisen tokenin.
    if sisalto.tuotanto_id != kayttaja.tuotanto_id or sisalto.rooli != kayttaja.rooli:
        raise _ei_kirjautunut()
    return kayttaja


async def nykyinen_rooli(kayttaja: Kayttaja = Depends(kirjautunut_kayttaja)) -> KayttajaRooli:
    return kayttaja.rooli


async def vaadi_kirjautuminen(
    request: Request,
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
) -> Kayttaja:
    """Reititintason vartija: 401 ilman voimassa olevaa tokenia, 403 jos
    KUSKI yrittää muokata. Backend estää muokkaukset riippumatta siitä,
    näyttääkö frontend napit."""
    if kayttaja.rooli == KayttajaRooli.KUSKI and request.method not in LUKUMETODIT:
        raise HTTPException(status_code=403, detail=EI_OIKEUTTA_MUOKATA)
    return kayttaja

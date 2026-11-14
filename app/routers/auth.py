"""Kirjautuminen: POST /auth/kirjaudu ja GET /auth/mina.

Muut reitit eivät vielä vaadi tokenia - se tulee ROADMAPin kohdassa K2.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    VirheellinenToken,
    hashaa_salasana,
    luo_token,
    pura_token,
    tarkista_salasana,
    tarvitseeko_uudelleenhashin,
)
from app.config import settings
from app.database import get_db
from app.models import Kayttaja
from app.schemas import KayttajaRead, KirjautumisPyynto, TokenVastaus

router = APIRouter(prefix="/auth", tags=["kirjautuminen"])

# Sama viesti kaikille epäonnistumisille: ei paljasteta, oliko email
# tuntematon, salasana väärä vai käyttäjä passivoitu.
VAARA_TUNNUS = "Väärä sähköposti tai salasana."
EI_KIRJAUTUNUT = "Kirjautuminen puuttuu tai istunto on vanhentunut."

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
    """Dependency: Authorization: Bearer <token> -> aktiivinen käyttäjä,
    muuten 401. K2 käyttää tätä kaikilla reiteillä."""
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
    return kayttaja


@router.post("/kirjaudu", response_model=TokenVastaus)
async def kirjaudu(pyynto: KirjautumisPyynto, db: AsyncSession = Depends(get_db)):
    email = pyynto.email.strip().lower()
    kayttaja = (
        await db.execute(select(Kayttaja).where(func.lower(Kayttaja.email) == email))
    ).scalar_one_or_none()

    # Salasana tarkistetaan aina (myös tuntemattomalle emailille), jotta
    # vastausaika ei paljasta, onko tunnus olemassa.
    oikein = tarkista_salasana(kayttaja.salasana_hash if kayttaja else None, pyynto.salasana)
    if kayttaja is None or not oikein or not kayttaja.aktiivinen:
        raise HTTPException(status_code=401, detail=VAARA_TUNNUS)

    if tarvitseeko_uudelleenhashin(kayttaja.salasana_hash):
        kayttaja.salasana_hash = hashaa_salasana(pyynto.salasana)
    # Tietokannan DateTime-sarakkeet ovat aikavyöhykkeettömiä: UTC ilman tzinfoa.
    kayttaja.viimeksi_kirjautunut = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(kayttaja)

    return TokenVastaus(
        access_token=luo_token(kayttaja),
        voimassa_s=settings.jwt_voimassa_h * 3600,
        kayttaja=KayttajaRead.model_validate(kayttaja),
    )


@router.get("/mina", response_model=KayttajaRead)
async def mina(kayttaja: Kayttaja = Depends(kirjautunut_kayttaja)):
    return kayttaja

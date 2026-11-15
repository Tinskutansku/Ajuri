from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Ajoneuvo, Kayttaja, Kuski, PaivaKuski
from app.omistus import hae_paiva, hae_paivan_rivi, rajaa_paivan_kautta, tarkista_viite
from app.rooli import kirjautunut_kayttaja
from app.schemas import PaivaKuskiCreate, PaivaKuskiRead

router = APIRouter(prefix="/paiva-kuskit", tags=["paiva-kuskit"])


async def _tarkista_kuski_aktiivinen(db: AsyncSession, kuski_id: int) -> None:
    kuski = await db.get(Kuski, kuski_id)
    if kuski is not None and not kuski.aktiivinen:
        raise HTTPException(status_code=422, detail="Poistettua kuskia ei voi liittää kuvauspäivään")


async def _tarkista_omat_viitteet(db: AsyncSession, data, kayttaja: Kayttaja) -> None:
    """Päivä ja rungossa viitatut rivit pitää olla käyttäjän omasta tuotannosta."""
    await hae_paiva(db, data.paiva_id, kayttaja)
    await tarkista_viite(db, Kuski, data.kuski_id, kayttaja, "Kuskia ei löytynyt")
    await tarkista_viite(db, Ajoneuvo, data.ajoneuvo_id, kayttaja, "Ajoneuvoa ei löytynyt")


@router.post("", response_model=PaivaKuskiRead, status_code=201)
async def luo_paiva_kuski(
    data: PaivaKuskiCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    await _tarkista_omat_viitteet(db, data, kayttaja)
    await _tarkista_kuski_aktiivinen(db, data.kuski_id)
    rivi = PaivaKuski(**data.model_dump())
    db.add(rivi)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.get("", response_model=list[PaivaKuskiRead])
async def listaa_paiva_kuskit(
    paiva_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    stmt = rajaa_paivan_kautta(select(PaivaKuski).order_by(PaivaKuski.id), PaivaKuski, kayttaja)
    if paiva_id is not None:
        await hae_paiva(db, paiva_id, kayttaja)
        stmt = stmt.where(PaivaKuski.paiva_id == paiva_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{rivi_id}", response_model=PaivaKuskiRead)
async def hae_paiva_kuski(
    rivi_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    rivi = await hae_paivan_rivi(db, PaivaKuski, rivi_id, kayttaja, "Päivän kuskia ei löytynyt")
    return rivi


@router.put("/{rivi_id}", response_model=PaivaKuskiRead)
async def paivita_paiva_kuski(
    rivi_id: int,
    data: PaivaKuskiCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    rivi = await hae_paivan_rivi(db, PaivaKuski, rivi_id, kayttaja, "Päivän kuskia ei löytynyt")
    await _tarkista_omat_viitteet(db, data, kayttaja)
    await _tarkista_kuski_aktiivinen(db, data.kuski_id)
    for kentta, arvo in data.model_dump().items():
        setattr(rivi, kentta, arvo)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.delete("/{rivi_id}", status_code=204)
async def poista_paiva_kuski(
    rivi_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    rivi = await hae_paivan_rivi(db, PaivaKuski, rivi_id, kayttaja, "Päivän kuskia ei löytynyt")
    await db.delete(rivi)
    await db.commit()

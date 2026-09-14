from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Kuski, PaivaKuski
from app.schemas import PaivaKuskiCreate, PaivaKuskiRead

router = APIRouter(prefix="/paiva-kuskit", tags=["paiva-kuskit"])


async def _tarkista_kuski_aktiivinen(db: AsyncSession, kuski_id: int) -> None:
    kuski = await db.get(Kuski, kuski_id)
    if kuski is not None and not kuski.aktiivinen:
        raise HTTPException(status_code=422, detail="Poistettua kuskia ei voi liittää kuvauspäivään")


@router.post("", response_model=PaivaKuskiRead, status_code=201)
async def luo_paiva_kuski(data: PaivaKuskiCreate, db: AsyncSession = Depends(get_db)):
    await _tarkista_kuski_aktiivinen(db, data.kuski_id)
    rivi = PaivaKuski(**data.model_dump())
    db.add(rivi)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.get("", response_model=list[PaivaKuskiRead])
async def listaa_paiva_kuskit(
    paiva_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(PaivaKuski).order_by(PaivaKuski.id)
    if paiva_id is not None:
        stmt = stmt.where(PaivaKuski.paiva_id == paiva_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{rivi_id}", response_model=PaivaKuskiRead)
async def hae_paiva_kuski(rivi_id: int, db: AsyncSession = Depends(get_db)):
    rivi = await db.get(PaivaKuski, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän kuskia ei löytynyt")
    return rivi


@router.put("/{rivi_id}", response_model=PaivaKuskiRead)
async def paivita_paiva_kuski(
    rivi_id: int, data: PaivaKuskiCreate, db: AsyncSession = Depends(get_db)
):
    rivi = await db.get(PaivaKuski, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän kuskia ei löytynyt")
    await _tarkista_kuski_aktiivinen(db, data.kuski_id)
    for kentta, arvo in data.model_dump().items():
        setattr(rivi, kentta, arvo)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.delete("/{rivi_id}", status_code=204)
async def poista_paiva_kuski(rivi_id: int, db: AsyncSession = Depends(get_db)):
    rivi = await db.get(PaivaKuski, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän kuskia ei löytynyt")
    await db.delete(rivi)
    await db.commit()

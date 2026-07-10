from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo
from app.schemas import HenkiloCreate, HenkiloRead

router = APIRouter(prefix="/henkilot", tags=["henkilot"])


@router.post("", response_model=HenkiloRead, status_code=201)
async def luo_henkilo(data: HenkiloCreate, db: AsyncSession = Depends(get_db)):
    henkilo = Henkilo(**data.model_dump())
    db.add(henkilo)
    await db.commit()
    await db.refresh(henkilo)
    return henkilo


@router.get("", response_model=list[HenkiloRead])
async def listaa_henkilot(
    tuotanto_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(Henkilo).order_by(Henkilo.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Henkilo.tuotanto_id == tuotanto_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{henkilo_id}", response_model=HenkiloRead)
async def hae_henkilo(henkilo_id: int, db: AsyncSession = Depends(get_db)):
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is None:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    return henkilo


@router.put("/{henkilo_id}", response_model=HenkiloRead)
async def paivita_henkilo(
    henkilo_id: int, data: HenkiloCreate, db: AsyncSession = Depends(get_db)
):
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is None:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(henkilo, kentta, arvo)
    await db.commit()
    await db.refresh(henkilo)
    return henkilo


@router.delete("/{henkilo_id}", status_code=204)
async def poista_henkilo(henkilo_id: int, db: AsyncSession = Depends(get_db)):
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is None:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    await db.delete(henkilo)
    await db.commit()

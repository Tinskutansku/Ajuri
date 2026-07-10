from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lokaatio
from app.schemas import LokaatioCreate, LokaatioRead

router = APIRouter(prefix="/lokaatiot", tags=["lokaatiot"])


@router.post("", response_model=LokaatioRead, status_code=201)
async def luo_lokaatio(data: LokaatioCreate, db: AsyncSession = Depends(get_db)):
    lokaatio = Lokaatio(**data.model_dump())
    db.add(lokaatio)
    await db.commit()
    await db.refresh(lokaatio)
    return lokaatio


@router.get("", response_model=list[LokaatioRead])
async def listaa_lokaatiot(
    tuotanto_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(Lokaatio).order_by(Lokaatio.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Lokaatio.tuotanto_id == tuotanto_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{lokaatio_id}", response_model=LokaatioRead)
async def hae_lokaatio(lokaatio_id: int, db: AsyncSession = Depends(get_db)):
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is None:
        raise HTTPException(status_code=404, detail="Lokaatiota ei löytynyt")
    return lokaatio


@router.put("/{lokaatio_id}", response_model=LokaatioRead)
async def paivita_lokaatio(
    lokaatio_id: int, data: LokaatioCreate, db: AsyncSession = Depends(get_db)
):
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is None:
        raise HTTPException(status_code=404, detail="Lokaatiota ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(lokaatio, kentta, arvo)
    await db.commit()
    await db.refresh(lokaatio)
    return lokaatio


@router.delete("/{lokaatio_id}", status_code=204)
async def poista_lokaatio(lokaatio_id: int, db: AsyncSession = Depends(get_db)):
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is None:
        raise HTTPException(status_code=404, detail="Lokaatiota ei löytynyt")
    await db.delete(lokaatio)
    await db.commit()

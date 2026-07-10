from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Tuotanto
from app.schemas import TuotantoCreate, TuotantoRead

router = APIRouter(prefix="/tuotannot", tags=["tuotannot"])


@router.post("", response_model=TuotantoRead, status_code=201)
async def luo_tuotanto(data: TuotantoCreate, db: AsyncSession = Depends(get_db)):
    tuotanto = Tuotanto(**data.model_dump())
    db.add(tuotanto)
    await db.commit()
    await db.refresh(tuotanto)
    return tuotanto


@router.get("", response_model=list[TuotantoRead])
async def listaa_tuotannot(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tuotanto).order_by(Tuotanto.id))
    return result.scalars().all()


@router.get("/{tuotanto_id}", response_model=TuotantoRead)
async def hae_tuotanto(tuotanto_id: int, db: AsyncSession = Depends(get_db)):
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")
    return tuotanto


@router.put("/{tuotanto_id}", response_model=TuotantoRead)
async def paivita_tuotanto(
    tuotanto_id: int, data: TuotantoCreate, db: AsyncSession = Depends(get_db)
):
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(tuotanto, kentta, arvo)
    await db.commit()
    await db.refresh(tuotanto)
    return tuotanto


@router.delete("/{tuotanto_id}", status_code=204)
async def poista_tuotanto(tuotanto_id: int, db: AsyncSession = Depends(get_db)):
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")
    await db.delete(tuotanto)
    await db.commit()

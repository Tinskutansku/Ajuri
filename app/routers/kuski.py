from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Kuski
from app.schemas import KuskiCreate, KuskiRead

router = APIRouter(prefix="/kuskit", tags=["kuskit"])


@router.post("", response_model=KuskiRead, status_code=201)
async def luo_kuski(data: KuskiCreate, db: AsyncSession = Depends(get_db)):
    kuski = Kuski(**data.model_dump())
    db.add(kuski)
    await db.commit()
    await db.refresh(kuski)
    return kuski


@router.get("", response_model=list[KuskiRead])
async def listaa_kuskit(
    tuotanto_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(Kuski).order_by(Kuski.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Kuski.tuotanto_id == tuotanto_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{kuski_id}", response_model=KuskiRead)
async def hae_kuski(kuski_id: int, db: AsyncSession = Depends(get_db)):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None:
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")
    return kuski


@router.put("/{kuski_id}", response_model=KuskiRead)
async def paivita_kuski(
    kuski_id: int, data: KuskiCreate, db: AsyncSession = Depends(get_db)
):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None:
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(kuski, kentta, arvo)
    await db.commit()
    await db.refresh(kuski)
    return kuski


@router.delete("/{kuski_id}", status_code=204)
async def poista_kuski(kuski_id: int, db: AsyncSession = Depends(get_db)):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None:
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")
    await db.delete(kuski)
    await db.commit()

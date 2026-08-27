from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Kuvauspaiva
from app.schemas import KuvauspaivaCreate, KuvauspaivaRead

router = APIRouter(prefix="/kuvauspaivat", tags=["kuvauspaivat"])


@router.post("", response_model=KuvauspaivaRead, status_code=201)
async def luo_kuvauspaiva(data: KuvauspaivaCreate, db: AsyncSession = Depends(get_db)):
    paiva = Kuvauspaiva(**data.model_dump())
    db.add(paiva)
    await db.commit()
    await db.refresh(paiva)
    return paiva


@router.get("", response_model=list[KuvauspaivaRead])
async def listaa_kuvauspaivat(
    tuotanto_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(Kuvauspaiva).order_by(Kuvauspaiva.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Kuvauspaiva.tuotanto_id == tuotanto_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{paiva_id}", response_model=KuvauspaivaRead)
async def hae_kuvauspaiva(paiva_id: int, db: AsyncSession = Depends(get_db)):
    paiva = await db.get(Kuvauspaiva, paiva_id)
    if paiva is None:
        raise HTTPException(status_code=404, detail="Kuvauspäivää ei löytynyt")
    return paiva


@router.put("/{paiva_id}", response_model=KuvauspaivaRead)
async def paivita_kuvauspaiva(
    paiva_id: int, data: KuvauspaivaCreate, db: AsyncSession = Depends(get_db)
):
    paiva = await db.get(Kuvauspaiva, paiva_id)
    if paiva is None:
        raise HTTPException(status_code=404, detail="Kuvauspäivää ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(paiva, kentta, arvo)
    await db.commit()
    await db.refresh(paiva)
    return paiva


@router.delete("/{paiva_id}", status_code=204)
async def poista_kuvauspaiva(paiva_id: int, db: AsyncSession = Depends(get_db)):
    paiva = await db.get(Kuvauspaiva, paiva_id)
    if paiva is None:
        raise HTTPException(status_code=404, detail="Kuvauspäivää ei löytynyt")
    await db.delete(paiva)
    await db.commit()

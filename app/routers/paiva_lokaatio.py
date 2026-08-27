from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import PaivaLokaatio
from app.schemas import PaivaLokaatioCreate, PaivaLokaatioRead

router = APIRouter(prefix="/paiva-lokaatiot", tags=["paiva-lokaatiot"])


@router.post("", response_model=PaivaLokaatioRead, status_code=201)
async def luo_paiva_lokaatio(data: PaivaLokaatioCreate, db: AsyncSession = Depends(get_db)):
    rivi = PaivaLokaatio(**data.model_dump())
    db.add(rivi)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.get("", response_model=list[PaivaLokaatioRead])
async def listaa_paiva_lokaatiot(
    paiva_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(PaivaLokaatio).order_by(PaivaLokaatio.id)
    if paiva_id is not None:
        stmt = stmt.where(PaivaLokaatio.paiva_id == paiva_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{rivi_id}", response_model=PaivaLokaatioRead)
async def hae_paiva_lokaatio(rivi_id: int, db: AsyncSession = Depends(get_db)):
    rivi = await db.get(PaivaLokaatio, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän lokaatiota ei löytynyt")
    return rivi


@router.put("/{rivi_id}", response_model=PaivaLokaatioRead)
async def paivita_paiva_lokaatio(
    rivi_id: int, data: PaivaLokaatioCreate, db: AsyncSession = Depends(get_db)
):
    rivi = await db.get(PaivaLokaatio, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän lokaatiota ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(rivi, kentta, arvo)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.delete("/{rivi_id}", status_code=204)
async def poista_paiva_lokaatio(rivi_id: int, db: AsyncSession = Depends(get_db)):
    rivi = await db.get(PaivaLokaatio, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän lokaatiota ei löytynyt")
    await db.delete(rivi)
    await db.commit()

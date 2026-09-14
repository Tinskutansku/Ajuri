from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo, PaivaHenkilo
from app.schemas import PaivaHenkiloCreate, PaivaHenkiloRead

router = APIRouter(prefix="/paiva-henkilot", tags=["paiva-henkilot"])


async def _tarkista_henkilo_aktiivinen(db: AsyncSession, henkilo_id: int) -> None:
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is not None and not henkilo.aktiivinen:
        raise HTTPException(status_code=422, detail="Poistettua henkilöä ei voi liittää kuvauspäivään")


@router.post("", response_model=PaivaHenkiloRead, status_code=201)
async def luo_paiva_henkilo(data: PaivaHenkiloCreate, db: AsyncSession = Depends(get_db)):
    await _tarkista_henkilo_aktiivinen(db, data.henkilo_id)
    rivi = PaivaHenkilo(**data.model_dump())
    db.add(rivi)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.get("", response_model=list[PaivaHenkiloRead])
async def listaa_paiva_henkilot(
    paiva_id: int | None = None, db: AsyncSession = Depends(get_db)
):
    stmt = select(PaivaHenkilo).order_by(PaivaHenkilo.id)
    if paiva_id is not None:
        stmt = stmt.where(PaivaHenkilo.paiva_id == paiva_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{rivi_id}", response_model=PaivaHenkiloRead)
async def hae_paiva_henkilo(rivi_id: int, db: AsyncSession = Depends(get_db)):
    rivi = await db.get(PaivaHenkilo, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän henkilöä ei löytynyt")
    return rivi


@router.put("/{rivi_id}", response_model=PaivaHenkiloRead)
async def paivita_paiva_henkilo(
    rivi_id: int, data: PaivaHenkiloCreate, db: AsyncSession = Depends(get_db)
):
    rivi = await db.get(PaivaHenkilo, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän henkilöä ei löytynyt")
    await _tarkista_henkilo_aktiivinen(db, data.henkilo_id)
    for kentta, arvo in data.model_dump().items():
        setattr(rivi, kentta, arvo)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.delete("/{rivi_id}", status_code=204)
async def poista_paiva_henkilo(rivi_id: int, db: AsyncSession = Depends(get_db)):
    rivi = await db.get(PaivaHenkilo, rivi_id)
    if rivi is None:
        raise HTTPException(status_code=404, detail="Päivän henkilöä ei löytynyt")
    await db.delete(rivi)
    await db.commit()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo, KayttajaRooli
from app.response_filter import HENKILO_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import nykyinen_rooli
from app.schemas import HenkiloCreate, HenkiloRead

router = APIRouter(prefix="/henkilot", tags=["henkilot"])


@router.post("", response_model=HenkiloRead, status_code=201)
async def luo_henkilo(
    data: HenkiloCreate,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    henkilo = Henkilo(**data.model_dump())
    db.add(henkilo)
    await db.commit()
    await db.refresh(henkilo)
    return json_vastaus(
        HenkiloRead.model_validate(henkilo), rooli, HENKILO_KUSKILTA_PIILOTETTAVAT, status_code=201
    )


@router.get("", response_model=list[HenkiloRead])
async def listaa_henkilot(
    tuotanto_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    stmt = select(Henkilo).order_by(Henkilo.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Henkilo.tuotanto_id == tuotanto_id)
    result = await db.execute(stmt)
    henkilot = result.scalars().all()
    return json_vastaus(
        [HenkiloRead.model_validate(h) for h in henkilot], rooli, HENKILO_KUSKILTA_PIILOTETTAVAT
    )


@router.get("/{henkilo_id}", response_model=HenkiloRead)
async def hae_henkilo(
    henkilo_id: int,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is None:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    return json_vastaus(HenkiloRead.model_validate(henkilo), rooli, HENKILO_KUSKILTA_PIILOTETTAVAT)


@router.put("/{henkilo_id}", response_model=HenkiloRead)
async def paivita_henkilo(
    henkilo_id: int,
    data: HenkiloCreate,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is None:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(henkilo, kentta, arvo)
    await db.commit()
    await db.refresh(henkilo)
    return json_vastaus(HenkiloRead.model_validate(henkilo), rooli, HENKILO_KUSKILTA_PIILOTETTAVAT)


@router.delete("/{henkilo_id}", status_code=204)
async def poista_henkilo(henkilo_id: int, db: AsyncSession = Depends(get_db)):
    henkilo = await db.get(Henkilo, henkilo_id)
    if henkilo is None:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    await db.delete(henkilo)
    await db.commit()

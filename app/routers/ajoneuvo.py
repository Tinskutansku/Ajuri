from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Ajoneuvo, Kayttaja
from app.omistus import hae_tuotannon_rivi, rajaa_tuotantoon, tarkista_tuotanto
from app.rooli import kirjautunut_kayttaja
from app.schemas import AjoneuvoCreate, AjoneuvoRead

router = APIRouter(prefix="/ajoneuvot", tags=["ajoneuvot"])


@router.post("", response_model=AjoneuvoRead, status_code=201)
async def luo_ajoneuvo(
    data: AjoneuvoCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    tarkista_tuotanto(data.tuotanto_id, kayttaja)
    ajoneuvo = Ajoneuvo(**data.model_dump())
    db.add(ajoneuvo)
    await db.commit()
    await db.refresh(ajoneuvo)
    return ajoneuvo


@router.get("", response_model=list[AjoneuvoRead])
async def listaa_ajoneuvot(
    tuotanto_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    stmt = rajaa_tuotantoon(select(Ajoneuvo).order_by(Ajoneuvo.id), Ajoneuvo, kayttaja)
    if tuotanto_id is not None:
        tarkista_tuotanto(tuotanto_id, kayttaja)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{ajoneuvo_id}", response_model=AjoneuvoRead)
async def hae_ajoneuvo(
    ajoneuvo_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    ajoneuvo = await hae_tuotannon_rivi(db, Ajoneuvo, ajoneuvo_id, kayttaja, "Ajoneuvoa ei löytynyt")
    return ajoneuvo


@router.put("/{ajoneuvo_id}", response_model=AjoneuvoRead)
async def paivita_ajoneuvo(
    ajoneuvo_id: int,
    data: AjoneuvoCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    ajoneuvo = await hae_tuotannon_rivi(db, Ajoneuvo, ajoneuvo_id, kayttaja, "Ajoneuvoa ei löytynyt")
    tarkista_tuotanto(data.tuotanto_id, kayttaja)
    for kentta, arvo in data.model_dump().items():
        setattr(ajoneuvo, kentta, arvo)
    await db.commit()
    await db.refresh(ajoneuvo)
    return ajoneuvo


@router.delete("/{ajoneuvo_id}", status_code=204)
async def poista_ajoneuvo(
    ajoneuvo_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    ajoneuvo = await hae_tuotannon_rivi(db, Ajoneuvo, ajoneuvo_id, kayttaja, "Ajoneuvoa ei löytynyt")
    await db.delete(ajoneuvo)
    await db.commit()

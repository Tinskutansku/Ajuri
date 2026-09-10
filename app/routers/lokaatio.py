from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lokaatio
from app.schemas import LokaatioCreate, LokaatioRead
from app.services.geocoder_client import GeocoderClient, get_geocoder_client
from app.services.geokoodaus_cache import paivita_koordinaatit_put, taydenna_koordinaatit

router = APIRouter(prefix="/lokaatiot", tags=["lokaatiot"])


@router.post("", response_model=LokaatioRead, status_code=201)
async def luo_lokaatio(
    data: LokaatioCreate,
    db: AsyncSession = Depends(get_db),
    geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    lokaatio = Lokaatio(**data.model_dump())
    await taydenna_koordinaatit(db, geocoder, lokaatio)
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
    lokaatio_id: int,
    data: LokaatioCreate,
    db: AsyncSession = Depends(get_db),
    geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is None:
        raise HTTPException(status_code=404, detail="Lokaatiota ei löytynyt")

    annetut_kentat = data.model_fields_set
    edellinen_osoite, edellinen_lat, edellinen_lon = lokaatio.osoite, lokaatio.lat, lokaatio.lon

    for kentta, arvo in data.model_dump().items():
        setattr(lokaatio, kentta, arvo)

    await paivita_koordinaatit_put(
        db, geocoder, lokaatio, annetut_kentat, edellinen_osoite, edellinen_lat, edellinen_lon,
    )
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

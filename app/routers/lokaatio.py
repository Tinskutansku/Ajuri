from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Kuvauspaiva, Lokaatio, PaivaLokaatio
from app.schemas import KayttoPaiva, LokaatioCreate, LokaatioRead
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
    tuotanto_id: int | None = None,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Lokaatio).order_by(Lokaatio.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Lokaatio.tuotanto_id == tuotanto_id)
    if not sisalla_passiiviset:
        stmt = stmt.where(Lokaatio.aktiivinen.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{lokaatio_id}", response_model=LokaatioRead)
async def hae_lokaatio(
    lokaatio_id: int, sisalla_passiiviset: bool = False, db: AsyncSession = Depends(get_db)
):
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is None or (not sisalla_passiiviset and not lokaatio.aktiivinen):
        raise HTTPException(status_code=404, detail="Lokaatiota ei löytynyt")
    return lokaatio


@router.get("/{lokaatio_id}/kaytto", response_model=list[KayttoPaiva])
async def hae_lokaatio_kaytto(lokaatio_id: int, db: AsyncSession = Depends(get_db)):
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is None:
        raise HTTPException(status_code=404, detail="Lokaatiota ei löytynyt")
    stmt = (
        select(Kuvauspaiva.id, Kuvauspaiva.pvm, Kuvauspaiva.paiva_nro)
        .join(PaivaLokaatio, PaivaLokaatio.paiva_id == Kuvauspaiva.id)
        .where(PaivaLokaatio.lokaatio_id == lokaatio_id)
        .order_by(Kuvauspaiva.pvm)
    )
    rivit = (await db.execute(stmt)).all()
    return [KayttoPaiva(paiva_id=r.id, pvm=r.pvm, paiva_nro=r.paiva_nro) for r in rivit]


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
    lokaatio.aktiivinen = False
    await db.commit()

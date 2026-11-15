from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Kayttaja, Lokaatio, PaivaLokaatio
from app.omistus import hae_paiva, hae_paivan_rivi, rajaa_paivan_kautta, tarkista_viite
from app.rooli import kirjautunut_kayttaja
from app.schemas import PaivaLokaatioCreate, PaivaLokaatioRead

router = APIRouter(prefix="/paiva-lokaatiot", tags=["paiva-lokaatiot"])


async def _tarkista_lokaatio_aktiivinen(db: AsyncSession, lokaatio_id: int) -> None:
    lokaatio = await db.get(Lokaatio, lokaatio_id)
    if lokaatio is not None and not lokaatio.aktiivinen:
        raise HTTPException(status_code=422, detail="Poistettua lokaatiota ei voi liittää kuvauspäivään")


async def _tarkista_omat_viitteet(db: AsyncSession, data, kayttaja: Kayttaja) -> None:
    """Päivä ja rungossa viitatut rivit pitää olla käyttäjän omasta tuotannosta."""
    await hae_paiva(db, data.paiva_id, kayttaja)
    await tarkista_viite(db, Lokaatio, data.lokaatio_id, kayttaja, "Lokaatiota ei löytynyt")


@router.post("", response_model=PaivaLokaatioRead, status_code=201)
async def luo_paiva_lokaatio(
    data: PaivaLokaatioCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    await _tarkista_omat_viitteet(db, data, kayttaja)
    await _tarkista_lokaatio_aktiivinen(db, data.lokaatio_id)
    rivi = PaivaLokaatio(**data.model_dump())
    db.add(rivi)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.get("", response_model=list[PaivaLokaatioRead])
async def listaa_paiva_lokaatiot(
    paiva_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    stmt = rajaa_paivan_kautta(select(PaivaLokaatio).order_by(PaivaLokaatio.id), PaivaLokaatio, kayttaja)
    if paiva_id is not None:
        await hae_paiva(db, paiva_id, kayttaja)
        stmt = stmt.where(PaivaLokaatio.paiva_id == paiva_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{rivi_id}", response_model=PaivaLokaatioRead)
async def hae_paiva_lokaatio(
    rivi_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    rivi = await hae_paivan_rivi(db, PaivaLokaatio, rivi_id, kayttaja, "Päivän lokaatiota ei löytynyt")
    return rivi


@router.put("/{rivi_id}", response_model=PaivaLokaatioRead)
async def paivita_paiva_lokaatio(
    rivi_id: int,
    data: PaivaLokaatioCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    rivi = await hae_paivan_rivi(db, PaivaLokaatio, rivi_id, kayttaja, "Päivän lokaatiota ei löytynyt")
    await _tarkista_omat_viitteet(db, data, kayttaja)
    await _tarkista_lokaatio_aktiivinen(db, data.lokaatio_id)
    for kentta, arvo in data.model_dump().items():
        setattr(rivi, kentta, arvo)
    await db.commit()
    await db.refresh(rivi)
    return rivi


@router.delete("/{rivi_id}", status_code=204)
async def poista_paiva_lokaatio(
    rivi_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    rivi = await hae_paivan_rivi(db, PaivaLokaatio, rivi_id, kayttaja, "Päivän lokaatiota ei löytynyt")
    await db.delete(rivi)
    await db.commit()

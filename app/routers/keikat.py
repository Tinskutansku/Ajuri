from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import KayttajaRooli, Keikka
from app.response_filter import KEIKKA_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import nykyinen_rooli
from app.schemas import KeikkaRead

router = APIRouter(prefix="/keikat", tags=["keikat"])


@router.get("", response_model=list[KeikkaRead])
async def listaa_keikat(
    versio_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    stmt = select(Keikka).order_by(Keikka.jarjestys)
    if versio_id is not None:
        stmt = stmt.where(Keikka.versio_id == versio_id)
    tulos = (await db.execute(stmt)).scalars().all()
    return json_vastaus(
        [KeikkaRead.model_validate(k) for k in tulos], rooli, KEIKKA_KUSKILTA_PIILOTETTAVAT
    )


@router.patch("/{keikka_id}/kuittaa", response_model=KeikkaRead)
async def kuittaa_keikka(
    keikka_id: int,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    keikka = await db.get(Keikka, keikka_id)
    if keikka is None:
        raise HTTPException(status_code=404, detail="Keikkaa ei löytynyt")
    keikka.kuitattu = True
    await db.commit()
    await db.refresh(keikka)
    return json_vastaus(KeikkaRead.model_validate(keikka), rooli, KEIKKA_KUSKILTA_PIILOTETTAVAT)

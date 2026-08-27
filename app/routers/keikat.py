from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Keikka
from app.schemas import KeikkaRead

router = APIRouter(prefix="/keikat", tags=["keikat"])


@router.patch("/{keikka_id}/kuittaa", response_model=KeikkaRead)
async def kuittaa_keikka(keikka_id: int, db: AsyncSession = Depends(get_db)):
    keikka = await db.get(Keikka, keikka_id)
    if keikka is None:
        raise HTTPException(status_code=404, detail="Keikkaa ei löytynyt")
    keikka.kuitattu = True
    await db.commit()
    await db.refresh(keikka)
    return keikka

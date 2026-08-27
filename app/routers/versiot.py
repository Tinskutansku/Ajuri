from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AjolistaVersio
from app.schemas import AjolistaVersioRead

router = APIRouter(prefix="/versiot", tags=["versiot"])


@router.post("/{versio_id}/julkaise", response_model=AjolistaVersioRead)
async def julkaise_versio(versio_id: int, db: AsyncSession = Depends(get_db)):
    versio = await db.get(AjolistaVersio, versio_id)
    if versio is None:
        raise HTTPException(status_code=404, detail="Versiota ei löytynyt")

    await db.execute(
        update(AjolistaVersio)
        .where(AjolistaVersio.paiva_id == versio.paiva_id, AjolistaVersio.id != versio_id)
        .values(julkaistu=False)
    )
    versio.julkaistu = True
    await db.commit()
    await db.refresh(versio)
    return versio

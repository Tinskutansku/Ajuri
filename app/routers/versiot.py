from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AjolistaVersio
from app.schemas import AjolistaVersioRead

router = APIRouter(prefix="/versiot", tags=["versiot"])

# Call sheet -käytännön mukainen väriketju (docs/tuotekartta.md, vaihe B2).
# Kun neljä loppuu kesken, kierretään numeroituna: "2. WHITE", "2. BLUE"...
VARIT = ["WHITE", "BLUE", "PINK", "YELLOW"]


def _seuraava_tunniste(kaytetyt_lkm: int) -> str:
    kierros, index = divmod(kaytetyt_lkm, len(VARIT))
    vari = VARIT[index]
    return vari if kierros == 0 else f"{kierros + 1}. {vari}"


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

    if versio.tunniste is None:
        kaytetyt_lkm = (
            await db.execute(
                select(func.count())
                .select_from(AjolistaVersio)
                .where(
                    AjolistaVersio.paiva_id == versio.paiva_id,
                    AjolistaVersio.tunniste.is_not(None),
                )
            )
        ).scalar_one()
        versio.tunniste = _seuraava_tunniste(kaytetyt_lkm)

    await db.commit()
    await db.refresh(versio)
    return versio

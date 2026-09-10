from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AjolistaVersio, KayttajaRooli
from app.response_filter import AJOLISTAVERSIO_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import nykyinen_rooli
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
async def julkaise_versio(
    versio_id: int,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
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
    return json_vastaus(
        AjolistaVersioRead.model_validate(versio), rooli, AJOLISTAVERSIO_KUSKILTA_PIILOTETTAVAT
    )


@router.get("", response_model=list[AjolistaVersioRead])
async def listaa_versiot(
    paiva_id: int | None = None,
    julkaistu: bool | None = None,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    stmt = select(AjolistaVersio).order_by(AjolistaVersio.versio_nro)
    if paiva_id is not None:
        stmt = stmt.where(AjolistaVersio.paiva_id == paiva_id)
    if julkaistu is not None:
        stmt = stmt.where(AjolistaVersio.julkaistu.is_(julkaistu))
    tulos = (await db.execute(stmt)).scalars().all()
    return json_vastaus(
        [AjolistaVersioRead.model_validate(v) for v in tulos], rooli, AJOLISTAVERSIO_KUSKILTA_PIILOTETTAVAT
    )


@router.get("/{versio_id}", response_model=AjolistaVersioRead)
async def hae_versio(
    versio_id: int,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    versio = await db.get(AjolistaVersio, versio_id)
    if versio is None:
        raise HTTPException(status_code=404, detail="Versiota ei löytynyt")
    return json_vastaus(
        AjolistaVersioRead.model_validate(versio), rooli, AJOLISTAVERSIO_KUSKILTA_PIILOTETTAVAT
    )

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AjolistaVersio, Kayttaja, KayttajaRooli, Keikka, Kuvauspaiva
from app.omistus import hae_keikka, hae_versio, rajaa_kuskin_keikat
from app.response_filter import KEIKKA_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import kirjautunut_kayttaja, nykyinen_rooli
from app.schemas import KeikkaRead

router = APIRouter(prefix="/keikat", tags=["keikat"])


@router.get("", response_model=list[KeikkaRead])
async def listaa_keikat(
    versio_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    stmt = (
        select(Keikka)
        .join(AjolistaVersio, AjolistaVersio.id == Keikka.versio_id)
        .join(Kuvauspaiva, Kuvauspaiva.id == AjolistaVersio.paiva_id)
        .where(Kuvauspaiva.tuotanto_id == kayttaja.tuotanto_id)
        .order_by(Keikka.jarjestys)
    )
    if versio_id is not None:
        await hae_versio(db, versio_id, kayttaja)
        stmt = stmt.where(Keikka.versio_id == versio_id)
    stmt = rajaa_kuskin_keikat(stmt, kayttaja)
    tulos = (await db.execute(stmt)).scalars().all()
    return json_vastaus(
        [KeikkaRead.model_validate(k) for k in tulos], rooli, KEIKKA_KUSKILTA_PIILOTETTAVAT
    )


@router.patch("/{keikka_id}/kuittaa", response_model=KeikkaRead)
async def kuittaa_keikka(
    keikka_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    keikka = await hae_keikka(db, keikka_id, kayttaja, "Keikkaa ei löytynyt")
    keikka.kuitattu = True
    await db.commit()
    await db.refresh(keikka)
    return json_vastaus(KeikkaRead.model_validate(keikka), rooli, KEIKKA_KUSKILTA_PIILOTETTAVAT)

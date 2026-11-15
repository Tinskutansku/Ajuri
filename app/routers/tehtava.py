from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo, Kayttaja, Kuski, Tehtava
from app.omistus import hae_paiva, hae_paivan_rivi, rajaa_paivan_kautta, tarkista_viite
from app.rooli import kirjautunut_kayttaja
from app.schemas import TehtavaCreate, TehtavaRead

router = APIRouter(prefix="/tehtavat", tags=["tehtavat"])


async def _tarkista_omat_viitteet(db: AsyncSession, data, kayttaja: Kayttaja) -> None:
    """Päivä ja rungossa viitatut rivit pitää olla käyttäjän omasta tuotannosta."""
    await hae_paiva(db, data.paiva_id, kayttaja)
    await tarkista_viite(db, Henkilo, data.henkilo_id, kayttaja, "Henkilöä ei löytynyt")
    await tarkista_viite(db, Kuski, data.lukittu_kuski_id, kayttaja, "Kuskia ei löytynyt")


@router.post("", response_model=TehtavaRead, status_code=201)
async def luo_tehtava(
    data: TehtavaCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    await _tarkista_omat_viitteet(db, data, kayttaja)
    tehtava = Tehtava(**data.model_dump())
    db.add(tehtava)
    await db.commit()
    await db.refresh(tehtava)
    return tehtava


@router.get("", response_model=list[TehtavaRead])
async def listaa_tehtavat(
    paiva_id: int | None = None,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    stmt = rajaa_paivan_kautta(select(Tehtava).order_by(Tehtava.id), Tehtava, kayttaja)
    if paiva_id is not None:
        await hae_paiva(db, paiva_id, kayttaja)
        stmt = stmt.where(Tehtava.paiva_id == paiva_id)
    if not sisalla_passiiviset:
        stmt = stmt.where(Tehtava.aktiivinen.is_(True))
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{tehtava_id}", response_model=TehtavaRead)
async def hae_tehtava(
    tehtava_id: int,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    tehtava = await hae_paivan_rivi(db, Tehtava, tehtava_id, kayttaja, "Tehtävää ei löytynyt")
    if not sisalla_passiiviset and not tehtava.aktiivinen:
        raise HTTPException(status_code=404, detail="Tehtävää ei löytynyt")
    return tehtava


@router.put("/{tehtava_id}", response_model=TehtavaRead)
async def paivita_tehtava(
    tehtava_id: int,
    data: TehtavaCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    tehtava = await hae_paivan_rivi(db, Tehtava, tehtava_id, kayttaja, "Tehtävää ei löytynyt")
    await _tarkista_omat_viitteet(db, data, kayttaja)
    for kentta, arvo in data.model_dump().items():
        setattr(tehtava, kentta, arvo)
    await db.commit()
    await db.refresh(tehtava)
    return tehtava


@router.delete("/{tehtava_id}", status_code=204)
async def poista_tehtava(
    tehtava_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    tehtava = await hae_paivan_rivi(db, Tehtava, tehtava_id, kayttaja, "Tehtävää ei löytynyt")
    tehtava.aktiivinen = False
    await db.commit()

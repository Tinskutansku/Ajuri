from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Tehtava
from app.schemas import TehtavaCreate, TehtavaRead

router = APIRouter(prefix="/tehtavat", tags=["tehtavat"])


@router.post("", response_model=TehtavaRead, status_code=201)
async def luo_tehtava(data: TehtavaCreate, db: AsyncSession = Depends(get_db)):
    tehtava = Tehtava(**data.model_dump())
    db.add(tehtava)
    await db.commit()
    await db.refresh(tehtava)
    return tehtava


@router.get("", response_model=list[TehtavaRead])
async def listaa_tehtavat(paiva_id: int | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Tehtava).order_by(Tehtava.id)
    if paiva_id is not None:
        stmt = stmt.where(Tehtava.paiva_id == paiva_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{tehtava_id}", response_model=TehtavaRead)
async def hae_tehtava(tehtava_id: int, db: AsyncSession = Depends(get_db)):
    tehtava = await db.get(Tehtava, tehtava_id)
    if tehtava is None:
        raise HTTPException(status_code=404, detail="Tehtävää ei löytynyt")
    return tehtava


@router.put("/{tehtava_id}", response_model=TehtavaRead)
async def paivita_tehtava(
    tehtava_id: int, data: TehtavaCreate, db: AsyncSession = Depends(get_db)
):
    tehtava = await db.get(Tehtava, tehtava_id)
    if tehtava is None:
        raise HTTPException(status_code=404, detail="Tehtävää ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(tehtava, kentta, arvo)
    await db.commit()
    await db.refresh(tehtava)
    return tehtava


@router.delete("/{tehtava_id}", status_code=204)
async def poista_tehtava(tehtava_id: int, db: AsyncSession = Depends(get_db)):
    tehtava = await db.get(Tehtava, tehtava_id)
    if tehtava is None:
        raise HTTPException(status_code=404, detail="Tehtävää ei löytynyt")
    await db.delete(tehtava)
    await db.commit()

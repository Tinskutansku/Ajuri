from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import KayttajaRooli, Kuski, Kuvauspaiva, PaivaKuski
from app.response_filter import KUSKI_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import nykyinen_rooli
from app.schemas import KayttoPaiva, KuskiCreate, KuskiRead
from app.services.geocoder_client import GeocoderClient, get_geocoder_client
from app.services.geokoodaus_cache import paivita_koordinaatit_put, taydenna_koordinaatit

router = APIRouter(prefix="/kuskit", tags=["kuskit"])

_KOTI_KENTAT = {"osoite_kentta": "koti_osoite", "lat_kentta": "koti_lat", "lon_kentta": "koti_lon"}


@router.post("", response_model=KuskiRead, status_code=201)
async def luo_kuski(
    data: KuskiCreate,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
    geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    kuski = Kuski(**data.model_dump())
    await taydenna_koordinaatit(db, geocoder, kuski, **_KOTI_KENTAT)
    db.add(kuski)
    await db.commit()
    await db.refresh(kuski)
    return json_vastaus(
        KuskiRead.model_validate(kuski), rooli, KUSKI_KUSKILTA_PIILOTETTAVAT, status_code=201
    )


@router.get("", response_model=list[KuskiRead])
async def listaa_kuskit(
    tuotanto_id: int | None = None,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    stmt = select(Kuski).order_by(Kuski.id)
    if tuotanto_id is not None:
        stmt = stmt.where(Kuski.tuotanto_id == tuotanto_id)
    if not sisalla_passiiviset:
        stmt = stmt.where(Kuski.aktiivinen.is_(True))
    result = await db.execute(stmt)
    kuskit = result.scalars().all()
    return json_vastaus(
        [KuskiRead.model_validate(k) for k in kuskit], rooli, KUSKI_KUSKILTA_PIILOTETTAVAT
    )


@router.get("/{kuski_id}", response_model=KuskiRead)
async def hae_kuski(
    kuski_id: int,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None or (not sisalla_passiiviset and not kuski.aktiivinen):
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")
    return json_vastaus(KuskiRead.model_validate(kuski), rooli, KUSKI_KUSKILTA_PIILOTETTAVAT)


@router.get("/{kuski_id}/kaytto", response_model=list[KayttoPaiva])
async def hae_kuski_kaytto(kuski_id: int, db: AsyncSession = Depends(get_db)):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None:
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")
    stmt = (
        select(Kuvauspaiva.id, Kuvauspaiva.pvm, Kuvauspaiva.paiva_nro)
        .join(PaivaKuski, PaivaKuski.paiva_id == Kuvauspaiva.id)
        .where(PaivaKuski.kuski_id == kuski_id)
        .order_by(Kuvauspaiva.pvm)
    )
    rivit = (await db.execute(stmt)).all()
    return [KayttoPaiva(paiva_id=r.id, pvm=r.pvm, paiva_nro=r.paiva_nro) for r in rivit]


@router.put("/{kuski_id}", response_model=KuskiRead)
async def paivita_kuski(
    kuski_id: int,
    data: KuskiCreate,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
    geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None:
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")

    annetut_kentat = data.model_fields_set
    edellinen_osoite, edellinen_lat, edellinen_lon = kuski.koti_osoite, kuski.koti_lat, kuski.koti_lon

    for kentta, arvo in data.model_dump().items():
        setattr(kuski, kentta, arvo)

    await paivita_koordinaatit_put(
        db, geocoder, kuski, annetut_kentat, edellinen_osoite, edellinen_lat, edellinen_lon,
        **_KOTI_KENTAT,
    )
    await db.commit()
    await db.refresh(kuski)
    return json_vastaus(KuskiRead.model_validate(kuski), rooli, KUSKI_KUSKILTA_PIILOTETTAVAT)


@router.delete("/{kuski_id}", status_code=204)
async def poista_kuski(kuski_id: int, db: AsyncSession = Depends(get_db)):
    kuski = await db.get(Kuski, kuski_id)
    if kuski is None:
        raise HTTPException(status_code=404, detail="Kuskia ei löytynyt")
    kuski.aktiivinen = False
    await db.commit()

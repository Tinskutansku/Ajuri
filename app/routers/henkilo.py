from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo, Kayttaja, KayttajaRooli, Kuvauspaiva, PaivaHenkilo
from app.omistus import hae_tuotannon_rivi, rajaa_tuotantoon, tarkista_tuotanto
from app.rooli import kirjautunut_kayttaja, nykyinen_rooli
from app.response_filter import HENKILO_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.schemas import HenkiloCreate, HenkiloRead, KayttoPaiva
from app.services.geocoder_client import GeocoderClient, get_geocoder_client
from app.services.geokoodaus_cache import paivita_koordinaatit_put, taydenna_koordinaatit

router = APIRouter(prefix="/henkilot", tags=["henkilot"])


@router.post("", response_model=HenkiloRead, status_code=201)
async def luo_henkilo(
    data: HenkiloCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
    geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    tarkista_tuotanto(data.tuotanto_id, kayttaja)
    henkilo = Henkilo(**data.model_dump())
    await taydenna_koordinaatit(db, geocoder, henkilo)
    db.add(henkilo)
    await db.commit()
    await db.refresh(henkilo)
    return json_vastaus(
        HenkiloRead.model_validate(henkilo), rooli, HENKILO_KUSKILTA_PIILOTETTAVAT, status_code=201
    )


@router.get("", response_model=list[HenkiloRead])
async def listaa_henkilot(
    tuotanto_id: int | None = None,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    stmt = rajaa_tuotantoon(select(Henkilo).order_by(Henkilo.id), Henkilo, kayttaja)
    if tuotanto_id is not None:
        tarkista_tuotanto(tuotanto_id, kayttaja)
    if not sisalla_passiiviset:
        stmt = stmt.where(Henkilo.aktiivinen.is_(True))
    result = await db.execute(stmt)
    henkilot = result.scalars().all()
    return json_vastaus(
        [HenkiloRead.model_validate(h) for h in henkilot], rooli, HENKILO_KUSKILTA_PIILOTETTAVAT
    )


@router.get("/{henkilo_id}", response_model=HenkiloRead)
async def hae_henkilo(
    henkilo_id: int,
    sisalla_passiiviset: bool = False,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    henkilo = await hae_tuotannon_rivi(db, Henkilo, henkilo_id, kayttaja, "Henkilöä ei löytynyt")
    if not sisalla_passiiviset and not henkilo.aktiivinen:
        raise HTTPException(status_code=404, detail="Henkilöä ei löytynyt")
    return json_vastaus(HenkiloRead.model_validate(henkilo), rooli, HENKILO_KUSKILTA_PIILOTETTAVAT)


@router.get("/{henkilo_id}/kaytto", response_model=list[KayttoPaiva])
async def hae_henkilo_kaytto(
    henkilo_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    await hae_tuotannon_rivi(db, Henkilo, henkilo_id, kayttaja, "Henkilöä ei löytynyt")
    stmt = (
        select(Kuvauspaiva.id, Kuvauspaiva.pvm, Kuvauspaiva.paiva_nro)
        .join(PaivaHenkilo, PaivaHenkilo.paiva_id == Kuvauspaiva.id)
        .where(PaivaHenkilo.henkilo_id == henkilo_id)
        .order_by(Kuvauspaiva.pvm)
    )
    rivit = (await db.execute(stmt)).all()
    return [KayttoPaiva(paiva_id=r.id, pvm=r.pvm, paiva_nro=r.paiva_nro) for r in rivit]


@router.put("/{henkilo_id}", response_model=HenkiloRead)
async def paivita_henkilo(
    henkilo_id: int,
    data: HenkiloCreate,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
    geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    henkilo = await hae_tuotannon_rivi(db, Henkilo, henkilo_id, kayttaja, "Henkilöä ei löytynyt")

    annetut_kentat = data.model_fields_set
    edellinen_osoite, edellinen_lat, edellinen_lon = henkilo.osoite, henkilo.lat, henkilo.lon

    tarkista_tuotanto(data.tuotanto_id, kayttaja)
    for kentta, arvo in data.model_dump().items():
        setattr(henkilo, kentta, arvo)

    await paivita_koordinaatit_put(
        db, geocoder, henkilo, annetut_kentat, edellinen_osoite, edellinen_lat, edellinen_lon,
    )
    await db.commit()
    await db.refresh(henkilo)
    return json_vastaus(HenkiloRead.model_validate(henkilo), rooli, HENKILO_KUSKILTA_PIILOTETTAVAT)


@router.delete("/{henkilo_id}", status_code=204)
async def poista_henkilo(
    henkilo_id: int,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    henkilo = await hae_tuotannon_rivi(db, Henkilo, henkilo_id, kayttaja, "Henkilöä ei löytynyt")
    henkilo.aktiivinen = False
    await db.commit()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo, Kuski, Lokaatio, Tuotanto
from app.schemas import GeokoodausTulos, TuotantoCreate, TuotantoRead
from app.services.geocoder_client import GeocoderClient, get_geocoder_client
from app.services.geokoodaus_cache import normalisoi_avain, on_tuore_kielteinen_osuma, taydenna_koordinaatit

router = APIRouter(prefix="/tuotannot", tags=["tuotannot"])


@router.post("", response_model=TuotantoRead, status_code=201)
async def luo_tuotanto(data: TuotantoCreate, db: AsyncSession = Depends(get_db)):
    tuotanto = Tuotanto(**data.model_dump())
    db.add(tuotanto)
    await db.commit()
    await db.refresh(tuotanto)
    return tuotanto


@router.get("", response_model=list[TuotantoRead])
async def listaa_tuotannot(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tuotanto).order_by(Tuotanto.id))
    return result.scalars().all()


@router.get("/{tuotanto_id}", response_model=TuotantoRead)
async def hae_tuotanto(tuotanto_id: int, db: AsyncSession = Depends(get_db)):
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")
    return tuotanto


@router.put("/{tuotanto_id}", response_model=TuotantoRead)
async def paivita_tuotanto(
    tuotanto_id: int, data: TuotantoCreate, db: AsyncSession = Depends(get_db)
):
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")
    for kentta, arvo in data.model_dump().items():
        setattr(tuotanto, kentta, arvo)
    await db.commit()
    await db.refresh(tuotanto)
    return tuotanto


@router.delete("/{tuotanto_id}", status_code=204)
async def poista_tuotanto(tuotanto_id: int, db: AsyncSession = Depends(get_db)):
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")
    await db.delete(tuotanto)
    await db.commit()


@router.post("/{tuotanto_id}/geokoodaa", response_model=GeokoodausTulos)
async def geokoodaa_tuotanto(
    tuotanto_id: int, raja: int = 15,
    db: AsyncSession = Depends(get_db), geocoder: GeocoderClient = Depends(get_geocoder_client),
):
    """Täydentää tuotannon kaikki koordinaatittomat henkilöt/kuskit/
    lokaatiot kerralla (Excel-tuonnin jälkeen), docs/tuotekartta.md
    vaihe E.

    raja oletuksena 15: Nominatim sallii 1 kutsun/s, joten suurempi arvo
    pitäisi HTTP-pyyntöä auki yli minuutin - moni selain/proxy/käänteis-
    proxy katkaisisi sen. Kutsu endpointtia uudestaan jaljella-laskurin
    ohjaamana kunnes se on 0.

    epaonnistui sisältää sekä "geokooderi vastasi mutta ei löytänyt
    osoitetta" (cachetaan negatiivisena TTL:n ajaksi) että "geokooderi ei
    vastannut / heitti poikkeuksen" (EI cachetta, yritetään automaattisesti
    uudestaan seuraavalla kutsulla) - näitä ei eroteta laskurissa, mutta
    ne käyttäytyvät eri tavalla jatkossa.

    jaljella tarkoittaa "koordinaatittomia rivejä joita EI yritetty tässä
    kutsussa" - sekä eräbudjetin ulkopuolelle jääneet että rivit joilla on
    tuore negatiivinen Geokoodi-osuma (niitä ei edes yritetä, jottei tuo
    koko budjettia loppuun pysyvästi epäonnistuvilta osoitteilta) tai
    joiden osoite ei ole koskaan geokoodattavissa (näitä ei lasketa
    jaljella:än vaan epaonnistui:in, koska niitä ei kannata yrittää
    koskaan uudestaan)."""
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise HTTPException(status_code=404, detail="Tuotantoa ei löytynyt")

    def koordinaatiton_kysely(malli, osoite_k, lat_k, lon_k):
        osoite_sar = getattr(malli, osoite_k)
        return select(malli).where(
            malli.tuotanto_id == tuotanto_id,
            osoite_sar.is_not(None), osoite_sar != "",
            getattr(malli, lat_k).is_(None), getattr(malli, lon_k).is_(None),
        )

    kohteet = [
        (Henkilo, "osoite", "lat", "lon", "henkilot"),
        (Kuski, "koti_osoite", "koti_lat", "koti_lon", "kuskit"),
        (Lokaatio, "osoite", "lat", "lon", "lokaatiot"),
    ]

    laskurit = {f"{nimi}_paivitetty": 0 for *_, nimi in kohteet} | {
        f"{nimi}_epaonnistui": 0 for *_, nimi in kohteet
    }
    jaljella = 0
    budjetti = raja

    for malli, osoite_k, lat_k, lon_k, nimi in kohteet:
        kaikki = (await db.execute(koordinaatiton_kysely(malli, osoite_k, lat_k, lon_k))).scalars().all()

        yritettavat = []
        for rivi in kaikki:
            osoite_arvo = getattr(rivi, osoite_k)
            if normalisoi_avain(osoite_arvo) is None:
                # Ei koskaan geokoodattavissa (tyhjä/yli 300 merkkiä) -
                # ei kannata yrittää uudestaan koskaan, EI jaljella:än.
                laskurit[f"{nimi}_epaonnistui"] += 1
            elif await on_tuore_kielteinen_osuma(db, osoite_arvo):
                jaljella += 1  # ei yritetä - tuore kielteinen osuma
            else:
                yritettavat.append(rivi)

        for rivi in yritettavat:
            if budjetti <= 0:
                jaljella += 1  # ei yritetty - eräbudjetti loppui
                continue
            await taydenna_koordinaatit(db, geocoder, rivi, osoite_k, lat_k, lon_k)
            budjetti -= 1
            avain = f"{nimi}_paivitetty" if getattr(rivi, lat_k) is not None else f"{nimi}_epaonnistui"
            laskurit[avain] += 1

    await db.commit()
    return GeokoodausTulos(**laskurit, jaljella=jaljella)

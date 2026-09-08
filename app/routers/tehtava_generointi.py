"""POST /paivat/{paiva_id}/generoi-tehtavat (docs/tuotekartta.md, vaihe B).

Generoi kuljetustehtävät (nouto ennen calliä -> siirtymä lokaatioiden
välillä -> paluu wrapissa) päivän paiva_henkilo-riveistä. Poikkeusliput
oma_auto/ei_paluuta/siirtyy per henkilö ohjaavat mitä generoidaan.

Generoidut rivit merkitään generoitu=true. Uudelleenajo ei poista vanhoja
generoituja rivejä (soft delete: aktiivinen=false) vaan luo uudet niiden
tilalle - käsin luotuja tehtäviä ei koskaan kosketa, eivätkä vanhat
ajolistaversiot voi koskaan rikkoutua koska mihinkään riviin ei viitata
enää sen jälkeen kun se on poistettu kannasta (docs/tuotekartta.md,
vaihe B2).
"""

from datetime import datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import (
    AjolistaVersio,
    Kuvauspaiva,
    PaivaHenkilo,
    PaivaLokaatio,
    Tehtava,
    TehtavaTyyppi,
)
from app.schemas import TehtavaGenerointiVastaus

router = APIRouter(tags=["tehtava-generointi"])

PALUU_IKKUNA_MIN = 25
JULKAISTU_VAROITUS = (
    "Päivälle on julkaistu ajolistaversio, joka ei sisällä juuri generoituja "
    "tehtäviä — aja optimointi uudelleen jotta ne tulevat mukaan ajolistaan."
)


def _lisaa_minuutteja(klo: time, minuutit: int) -> time:
    return (datetime.combine(datetime.min, klo) + timedelta(minutes=minuutit)).time()


@router.post("/paivat/{paiva_id}/generoi-tehtavat", response_model=TehtavaGenerointiVastaus)
async def generoi_tehtavat(paiva_id: int, db: AsyncSession = Depends(get_db)):
    paiva = await db.get(Kuvauspaiva, paiva_id)
    if paiva is None:
        raise HTTPException(status_code=404, detail="Kuvauspäivää ei löytynyt")

    lokaatiot = (
        (
            await db.execute(
                select(PaivaLokaatio)
                .where(PaivaLokaatio.paiva_id == paiva_id)
                .options(selectinload(PaivaLokaatio.lokaatio))
                .order_by(PaivaLokaatio.jarjestys)
            )
        )
        .scalars()
        .all()
    )
    if not lokaatiot:
        raise HTTPException(
            status_code=422, detail="Päivälle ei ole määritetty lokaatioita"
        )

    paiva_henkilot = (
        (
            await db.execute(
                select(PaivaHenkilo)
                .where(PaivaHenkilo.paiva_id == paiva_id)
                .options(selectinload(PaivaHenkilo.henkilo))
            )
        )
        .scalars()
        .all()
    )

    ensimmainen = lokaatiot[0].lokaatio
    viimeinen = lokaatiot[-1].lokaatio

    uudet: list[Tehtava] = []
    for ph in paiva_henkilot:
        if ph.oma_auto:
            continue
        henkilo = ph.henkilo

        uudet.append(
            Tehtava(
                paiva_id=paiva_id,
                tyyppi=TehtavaTyyppi.HENKILO,
                nimi=f"Nouto: {henkilo.nimi}",
                henkilo_id=henkilo.id,
                henkiloita=1,
                mista_osoite=henkilo.osoite or "",
                mista_lat=henkilo.lat,
                mista_lon=henkilo.lon,
                mihin_osoite=ensimmainen.osoite or "",
                mihin_lat=ensimmainen.lat,
                mihin_lon=ensimmainen.lon,
                perilla_viimeistaan=ph.oma_call or paiva.call_time,
                generoitu=True,
                yksin=henkilo.oletus_yksin,
            )
        )

        if ph.siirtyy and len(lokaatiot) > 1:
            for edellinen, seuraava in zip(lokaatiot, lokaatiot[1:]):
                perilla = ph.siirtyma_klo or seuraava.siirtyma_klo
                uudet.append(
                    Tehtava(
                        paiva_id=paiva_id,
                        tyyppi=TehtavaTyyppi.SIIRTYMA,
                        nimi=f"Siirtymä: {henkilo.nimi} "
                             f"({edellinen.lokaatio.nimi} → {seuraava.lokaatio.nimi})",
                        henkilo_id=henkilo.id,
                        henkiloita=1,
                        mista_osoite=edellinen.lokaatio.osoite or "",
                        mista_lat=edellinen.lokaatio.lat,
                        mista_lon=edellinen.lokaatio.lon,
                        mihin_osoite=seuraava.lokaatio.osoite or "",
                        mihin_lat=seuraava.lokaatio.lat,
                        mihin_lon=seuraava.lokaatio.lon,
                        perilla_viimeistaan=perilla,
                        generoitu=True,
                        yksin=henkilo.oletus_yksin,
                    )
                )

        if not ph.ei_paluuta:
            if paiva.wrap_arvio is None:
                raise HTTPException(
                    status_code=422,
                    detail="Päivälle ei ole asetettu wrap_arvio-aikaa, "
                           "jota paluukyytien aikaikkuna tarvitsee",
                )
            lahto_lokaatio = viimeinen if ph.siirtyy else ensimmainen
            uudet.append(
                Tehtava(
                    paiva_id=paiva_id,
                    tyyppi=TehtavaTyyppi.PALUU,
                    nimi=f"Paluu: {henkilo.nimi}",
                    henkilo_id=henkilo.id,
                    henkiloita=1,
                    mista_osoite=lahto_lokaatio.osoite or "",
                    mista_lat=lahto_lokaatio.lat,
                    mista_lon=lahto_lokaatio.lon,
                    mihin_osoite=henkilo.osoite or "",
                    mihin_lat=henkilo.lat,
                    mihin_lon=henkilo.lon,
                    nouto_aikaisintaan=paiva.wrap_arvio,
                    nouto_viimeistaan=_lisaa_minuutteja(paiva.wrap_arvio, PALUU_IKKUNA_MIN),
                    generoitu=True,
                    yksin=henkilo.oletus_yksin,
                )
            )

    await db.execute(
        update(Tehtava)
        .where(
            Tehtava.paiva_id == paiva_id,
            Tehtava.generoitu.is_(True),
            Tehtava.aktiivinen.is_(True),
        )
        .values(aktiivinen=False)
    )
    db.add_all(uudet)
    await db.commit()
    for rivi in uudet:
        await db.refresh(rivi)

    on_julkaistu_versio = (
        await db.execute(
            select(AjolistaVersio.id)
            .where(AjolistaVersio.paiva_id == paiva_id, AjolistaVersio.julkaistu.is_(True))
            .limit(1)
        )
    ).scalar_one_or_none() is not None

    return TehtavaGenerointiVastaus(
        tehtavat=uudet,
        varoitus=JULKAISTU_VAROITUS if on_julkaistu_versio else None,
    )

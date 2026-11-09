from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AjolistaVersio, KayttajaRooli, Keikka, PaivaKuski
from app.response_filter import (
    AJOLISTAVERSIO_KUSKILTA_PIILOTETTAVAT,
    VERSIODIFF_KUSKILTA_PIILOTETTAVAT,
    json_vastaus,
)
from app.rooli import nykyinen_rooli
from app.schemas import AjolistaVersioRead, DiffKeikka, DiffKuski, VersioDiff

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


async def _versio_keikkoineen(db: AsyncSession, versio_id: int) -> AjolistaVersio:
    stmt = (
        select(AjolistaVersio)
        .where(AjolistaVersio.id == versio_id)
        .options(
            selectinload(AjolistaVersio.keikat).selectinload(Keikka.tehtava),
            selectinload(AjolistaVersio.keikat)
            .selectinload(Keikka.paiva_kuski)
            .selectinload(PaivaKuski.kuski),
        )
    )
    versio = (await db.execute(stmt)).scalar_one_or_none()
    if versio is None:
        raise HTTPException(status_code=404, detail=f"Versiota {versio_id} ei löytynyt")
    return versio


def _diff_keikka(a: Keikka | None, b: Keikka | None) -> DiffKeikka:
    tehtava = (b or a).tehtava
    return DiffKeikka(
        tehtava_id=tehtava.id,
        tehtava_nimi=tehtava.nimi,
        kuski_id_a=a.paiva_kuski.kuski_id if a else None,
        kuski_nimi_a=a.paiva_kuski.kuski.nimi if a else None,
        kuski_id_b=b.paiva_kuski.kuski_id if b else None,
        kuski_nimi_b=b.paiva_kuski.kuski.nimi if b else None,
        nouto_klo_a=a.nouto_klo if a else None,
        nouto_klo_b=b.nouto_klo if b else None,
        jatto_klo_a=a.jatto_klo if a else None,
        jatto_klo_b=b.jatto_klo if b else None,
    )


def laske_diff(a: AjolistaVersio, b: AjolistaVersio) -> VersioDiff:
    """Vertaa versiota a (vanha) versioon b (uusi). Keikat täsmätään
    tehtava_id:n perusteella. Kuski verrataan kuski_id:llä, ei
    paiva_kuski_id:llä, jotta sama ihminen tunnistetaan."""
    keikat_a = {k.tehtava_id: k for k in a.keikat}
    keikat_b = {k.tehtava_id: k for k in b.keikat}

    def jarjestysavain(d: DiffKeikka):
        klo = d.nouto_klo_b or d.nouto_klo_a
        return (klo is None, klo, d.tehtava_nimi, d.tehtava_id)

    siirtyneet, vaihtaneet, ennallaan = [], [], 0
    for tehtava_id in keikat_a.keys() & keikat_b.keys():
        ka, kb = keikat_a[tehtava_id], keikat_b[tehtava_id]
        ajat_muuttui = (ka.nouto_klo, ka.jatto_klo) != (kb.nouto_klo, kb.jatto_klo)
        kuski_muuttui = ka.paiva_kuski.kuski_id != kb.paiva_kuski.kuski_id
        if ajat_muuttui:
            siirtyneet.append(_diff_keikka(ka, kb))
        if kuski_muuttui:
            vaihtaneet.append(_diff_keikka(ka, kb))
        if not ajat_muuttui and not kuski_muuttui:
            ennallaan += 1

    uudet = [_diff_keikka(None, keikat_b[t]) for t in keikat_b.keys() - keikat_a.keys()]
    poistuneet = [_diff_keikka(keikat_a[t], None) for t in keikat_a.keys() - keikat_b.keys()]

    lkm: dict[int, list] = {}  # kuski_id -> [nimi, a, b]
    for indeksi, keikat in ((1, a.keikat), (2, b.keikat)):
        for k in keikat:
            rivi = lkm.setdefault(k.paiva_kuski.kuski_id, [k.paiva_kuski.kuski.nimi, 0, 0])
            rivi[indeksi] += 1
    kuskit = sorted(
        (
            DiffKuski(kuski_id=kid, kuski_nimi=nimi, keikkoja_a=na, keikkoja_b=nb, muutos=nb - na)
            for kid, (nimi, na, nb) in lkm.items()
            if na != nb
        ),
        key=lambda d: (d.kuski_nimi, d.kuski_id),
    )

    kustannusmuutos = (
        round(b.kokonaiskustannus_eur - a.kokonaiskustannus_eur, 2)
        if a.kokonaiskustannus_eur is not None and b.kokonaiskustannus_eur is not None
        else None
    )
    return VersioDiff(
        versio_a_id=a.id,
        versio_b_id=b.id,
        paiva_id=a.paiva_id,
        siirtyneet=sorted(siirtyneet, key=jarjestysavain),
        kuskia_vaihtaneet=sorted(vaihtaneet, key=jarjestysavain),
        uudet=sorted(uudet, key=jarjestysavain),
        poistuneet=sorted(poistuneet, key=jarjestysavain),
        ennallaan_lkm=ennallaan,
        kuskit=kuskit,
        kokonaiskustannus_a_eur=a.kokonaiskustannus_eur,
        kokonaiskustannus_b_eur=b.kokonaiskustannus_eur,
        kustannusmuutos_eur=kustannusmuutos,
    )


@router.get("/{versio_a_id}/diff/{versio_b_id}", response_model=VersioDiff)
async def versioiden_diff(
    versio_a_id: int,
    versio_b_id: int,
    db: AsyncSession = Depends(get_db),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    """Mitä muuttui versiosta a versioon b (a = vanha, b = uusi).
    Molempien versioiden pitää olla samalta päivältä."""
    a = await _versio_keikkoineen(db, versio_a_id)
    b = await _versio_keikkoineen(db, versio_b_id)
    if a.paiva_id != b.paiva_id:
        raise HTTPException(status_code=400, detail="Versiot ovat eri kuvauspäiviltä")
    return json_vastaus(laske_diff(a, b), rooli, VERSIODIFF_KUSKILTA_PIILOTETTAVAT)

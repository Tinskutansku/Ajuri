"""POST /paivat/{paiva_id}/optimoi (docs/optimoija-spec.md §1).

Lukee päivän datan tietokannasta, ratkaisee reitit OR-Toolsilla
(app.services.optimoija) ja tallentaa tuloksen uutena ajolista_versio-versiona.
"""

from datetime import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import AjolistaVersio, Henkilo, KayttajaRooli, Keikka, Kuvauspaiva, PaivaKuski, Tehtava, Tuotanto
from app.response_filter import OPTIMOINTIVASTAUS_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import nykyinen_rooli
from app.schemas import (
    KeikkaVastaus,
    KuskinAjolista,
    OptimointiPyynto,
    OptimointiVastaus,
    Sijoittamaton,
    Skenaario,
)
from app.services.matka_cache import hae_ajoajat, pyorista_piste
from app.services.optimoija import (
    KeikkaTulos,
    KuskiRow,
    OptimointiParametrit,
    TehtavaRow,
    analysoi_sijoittamattomat,
    koosta_kuskien_yhteenveto,
    ratkaise,
    vertaile_skenaarioita,
)
from app.services.router_client import RouterClient, get_router_client

router = APIRouter(tags=["optimointi"])


def _time_to_min(waktu: time | None) -> int | None:
    return None if waktu is None else waktu.hour * 60 + waktu.minute


def _min_to_time(minuutit: int) -> time:
    minuutit %= 24 * 60
    return time(hour=minuutit // 60, minute=minuutit % 60)


def _hhmm(minuutit: int) -> str:
    aika = _min_to_time(minuutit)
    return f"{aika.hour:02d}:{aika.minute:02d}"


def _parse_hhmm(teksti: str) -> int:
    h, m = teksti.split(":")
    return int(h) * 60 + int(m)


@router.post("/paivat/{paiva_id}/optimoi", response_model=OptimointiVastaus)
async def optimoi_paiva(
    paiva_id: int,
    pyynto: OptimointiPyynto,
    db: AsyncSession = Depends(get_db),
    router_client: RouterClient = Depends(get_router_client),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    paiva = await db.get(Kuvauspaiva, paiva_id)
    if paiva is None:
        raise HTTPException(status_code=404, detail="Kuvauspäivää ei löytynyt")
    tuotanto = await db.get(Tuotanto, paiva.tuotanto_id)

    kuski_rivit = (
        (
            await db.execute(
                select(PaivaKuski)
                .where(PaivaKuski.paiva_id == paiva_id, PaivaKuski.tarjolla.is_(True))
                .options(selectinload(PaivaKuski.kuski), selectinload(PaivaKuski.ajoneuvo))
            )
        )
        .scalars()
        .all()
    )
    for pk in kuski_rivit:
        if pk.ajoneuvo is None:
            raise HTTPException(
                status_code=422,
                detail=f"Kuskille {pk.kuski.nimi} ei ole valittu ajoneuvoa tälle päivälle",
            )
        if pk.kuski.koti_lat is None or pk.kuski.koti_lon is None:
            raise HTTPException(
                status_code=422, detail=f"Kuskilta {pk.kuski.nimi} puuttuu koti-koordinaatit"
            )

    kaikki_tehtavat = (
        (
            await db.execute(
                select(Tehtava).where(
                    Tehtava.paiva_id == paiva_id, Tehtava.aktiivinen.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    for teht in kaikki_tehtavat:
        if None in (teht.mista_lat, teht.mista_lon, teht.mihin_lat, teht.mihin_lon):
            raise HTTPException(
                status_code=422, detail=f"Tehtävältä '{teht.nimi}' puuttuu koordinaatit"
            )
    tehtava_by_id = {t.id: t for t in kaikki_tehtavat}

    henkilo_ids = {t.henkilo_id for t in kaikki_tehtavat if t.henkilo_id is not None}
    henkilo_bufferi_by_id: dict[int, int] = {}
    if henkilo_ids:
        henkilo_bufferi_by_id = dict(
            (
                await db.execute(
                    select(Henkilo.id, Henkilo.nouto_bufferi_min).where(Henkilo.id.in_(henkilo_ids))
                )
            ).all()
        )

    # --- Reoptimointi: pohjaversio + lukitut keikat ---
    nyt_min = _parse_hhmm(pyynto.nyt) if pyynto.nyt else None
    pohjaversio: AjolistaVersio | None = None
    pohja_keikat: list[Keikka] = []

    if nyt_min is not None:
        if pyynto.pohjaversio_id is not None:
            pohjaversio = await db.get(AjolistaVersio, pyynto.pohjaversio_id)
            if pohjaversio is None or pohjaversio.paiva_id != paiva_id:
                raise HTTPException(status_code=404, detail="Pohjaversiota ei löytynyt")
        else:
            pohjaversio = (
                (
                    await db.execute(
                        select(AjolistaVersio)
                        .where(
                            AjolistaVersio.paiva_id == paiva_id,
                            AjolistaVersio.julkaistu.is_(True),
                        )
                        .order_by(AjolistaVersio.versio_nro.desc())
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if pohjaversio is None:
                raise HTTPException(
                    status_code=400,
                    detail="Ei julkaistua pohjaversiota reoptimointiin — anna pohjaversio_id",
                )
        pohja_keikat = (
            (await db.execute(select(Keikka).where(Keikka.versio_id == pohjaversio.id)))
            .scalars()
            .all()
        )

    lukitut_map: dict[int, Keikka] = {}
    edellinen_kuski_map: dict[int, int] = {}
    for kk in pohja_keikat:
        if kk.kuitattu or _time_to_min(kk.nouto_klo) < nyt_min:
            lukitut_map[kk.tehtava_id] = kk
        else:
            edellinen_kuski_map[kk.tehtava_id] = kk.paiva_kuski_id

    # Lukitun keikan tehtävä on saatettu passivoida (soft delete) sen jälkeen
    # kun keikka luotiin - se ei silloin ole kaikki_tehtavat-listalla, vaikka
    # sitä yhä tarvitaan lukitun keikan näyttämiseen. Täydennä puuttuvat.
    puuttuvat_tehtava_id = set(lukitut_map) - set(tehtava_by_id)
    if puuttuvat_tehtava_id:
        lisatehtavat = (
            (await db.execute(select(Tehtava).where(Tehtava.id.in_(puuttuvat_tehtava_id))))
            .scalars()
            .all()
        )
        tehtava_by_id.update({t.id: t for t in lisatehtavat})

    # kuskin lähtötila: viimeisen lukitun keikan jättöpaikka/-aika, jos on
    kuskin_alkutila: dict[int, tuple[tuple[float, float], int]] = {}
    for kk in lukitut_map.values():
        jatto_min = _time_to_min(kk.jatto_klo)
        edellinen = kuskin_alkutila.get(kk.paiva_kuski_id)
        if edellinen is None or jatto_min > edellinen[1]:
            teht = tehtava_by_id[kk.tehtava_id]
            kuskin_alkutila[kk.paiva_kuski_id] = (
                pyorista_piste((teht.mihin_lat, teht.mihin_lon)),
                jatto_min,
            )

    ratkaistavat_tehtavat = [t for t in kaikki_tehtavat if t.id not in lukitut_map]

    # --- Rakenna kuskit ---
    kuskit = [
        KuskiRow(
            paiva_kuski_id=pk.id,
            kuski_id=pk.kuski_id,
            nimi=pk.kuski.nimi,
            sopimus=pk.kuski.sopimus,
            tuntihinta=(
                pk.kuski.tuntihinta_eur
                if pk.kuski.tuntihinta_eur is not None
                else tuotanto.tuntihinta_eur
            ),
            paikkoja=pk.ajoneuvo.mukavuuspaikat,
            aloitus=kuskin_alkutila.get(pk.id, (None, None))[0]
            or pyorista_piste((pk.kuski.koti_lat, pk.kuski.koti_lon)),
            vuoro_aikaisintaan=_time_to_min(pk.vuoro_aikaisintaan),
            vuoro_viimeistaan=_time_to_min(pk.vuoro_viimeistaan),
            aloitus_aika_min=kuskin_alkutila.get(pk.id, (None, None))[1],
            pickup_bufferi_min=pk.kuski.pickup_bufferi_min,
        )
        for pk in kuski_rivit
    ]

    # --- Rakenna tehtävät (lukitsemattomat) ---
    tehtavat = [
        TehtavaRow(
            id=teht.id,
            nimi=teht.nimi,
            mista=pyorista_piste((teht.mista_lat, teht.mista_lon)),
            mihin=pyorista_piste((teht.mihin_lat, teht.mihin_lon)),
            henkiloita=teht.henkiloita,
            nouto_aikaisintaan=_time_to_min(teht.nouto_aikaisintaan),
            nouto_viimeistaan=_time_to_min(teht.nouto_viimeistaan),
            perilla_aikaisintaan=_time_to_min(teht.perilla_aikaisintaan),
            perilla_viimeistaan=_time_to_min(teht.perilla_viimeistaan),
            lukittu_kuski_id=teht.lukittu_kuski_id,
            yksin=teht.yksin,
            edellinen_paiva_kuski_id=edellinen_kuski_map.get(teht.id),
            henkilo_bufferi_min=henkilo_bufferi_by_id.get(teht.henkilo_id, 0),
        )
        for teht in ratkaistavat_tehtavat
    ]

    # --- Ajoaikamatriisi (matka_cache + reititys-API) ---
    pisteet = [k.aloitus for k in kuskit]
    for teht in tehtavat:
        pisteet.append(teht.mista)
        pisteet.append(teht.mihin)
    ajoaika = await hae_ajoajat(db, pisteet, router_client)

    parametrit = OptimointiParametrit(
        aikaraja_s=pyynto.aikaraja_s,
        max_etuajassa_min=pyynto.max_etuajassa_min,
        max_kyytiaika_lisa_min=pyynto.max_kyytiaika_lisa_min,
    )

    tulos = ratkaise(tehtavat, kuskit, ajoaika, parametrit)

    skenaariot_data = None
    if pyynto.skenaariot:
        skenaariot_data = vertaile_skenaarioita(tehtavat, kuskit, ajoaika, parametrit)

    # --- Yhdistä lukitut + uudet keikat ---
    persistoinnin_lisatiedot: dict[int, tuple[bool, bool]] = {}  # tehtava_id -> (kasin_siirretty, kuitattu)
    yhdistetyt: list[KeikkaTulos] = list(tulos.keikat)
    for kk in lukitut_map.values():
        yhdistetyt.append(
            KeikkaTulos(
                tehtava_id=kk.tehtava_id,
                paiva_kuski_id=kk.paiva_kuski_id,
                nouto_min=_time_to_min(kk.nouto_klo),
                jatto_min=_time_to_min(kk.jatto_klo),
                lukittu=True,
            )
        )
        persistoinnin_lisatiedot[kk.tehtava_id] = (kk.kasin_siirretty, kk.kuitattu)

    yhteenveto = koosta_kuskien_yhteenveto(yhdistetyt, kuskit)
    kuski_by_id = {k.paiva_kuski_id: k for k in kuskit}

    # --- Tallenna uusi versio ---
    edellinen_versio_nro = (
        await db.execute(
            select(AjolistaVersio.versio_nro)
            .where(AjolistaVersio.paiva_id == paiva_id)
            .order_by(AjolistaVersio.versio_nro.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    versio_nro = (edellinen_versio_nro or 0) + 1

    uusi_versio = AjolistaVersio(
        paiva_id=paiva_id,
        versio_nro=versio_nro,
        kokonaiskustannus_eur=round(sum(y.lisakustannus_eur for y in yhteenveto), 2),
        julkaistu=False,
    )
    db.add(uusi_versio)
    await db.flush()

    keikka_rivit: list[Keikka] = []
    for y in yhteenveto:
        for jarjestys, kk in enumerate(y.keikat, start=1):
            kasin_siirretty, kuitattu = persistoinnin_lisatiedot.get(kk.tehtava_id, (False, False))
            keikka_rivit.append(
                Keikka(
                    versio_id=uusi_versio.id,
                    tehtava_id=kk.tehtava_id,
                    paiva_kuski_id=kk.paiva_kuski_id,
                    nouto_klo=_min_to_time(kk.nouto_min),
                    jatto_klo=_min_to_time(kk.jatto_min),
                    jarjestys=jarjestys,
                    kasin_siirretty=kasin_siirretty,
                    kuitattu=kuitattu,
                )
            )
    db.add_all(keikka_rivit)
    await db.commit()
    for rivi in keikka_rivit:
        await db.refresh(rivi)
    keikka_id_by_tehtava = {rivi.tehtava_id: rivi.id for rivi in keikka_rivit}

    lukittu_tehtava_ids = set(lukitut_map.keys())

    kuskien_ajolistat = [
        KuskinAjolista(
            paiva_kuski_id=y.paiva_kuski_id,
            nimi=kuski_by_id[y.paiva_kuski_id].nimi,
            sopimus=kuski_by_id[y.paiva_kuski_id].sopimus,
            vuoro_alku=_hhmm(y.alku_min),
            vuoro_loppu=_hhmm(y.loppu_min),
            kesto_min=y.kesto_min,
            lisakustannus_eur=y.lisakustannus_eur,
            keikat=[
                KeikkaVastaus(
                    keikka_id=keikka_id_by_tehtava[kk.tehtava_id],
                    tehtava_id=kk.tehtava_id,
                    nimi=tehtava_by_id[kk.tehtava_id].nimi,
                    nouto_klo=_hhmm(kk.nouto_min),
                    jatto_klo=_hhmm(kk.jatto_min),
                    mista=tehtava_by_id[kk.tehtava_id].mista_osoite,
                    mihin=tehtava_by_id[kk.tehtava_id].mihin_osoite,
                    kuitattu=persistoinnin_lisatiedot.get(kk.tehtava_id, (False, False))[1],
                    lukittu=kk.tehtava_id in lukittu_tehtava_ids,
                )
                for kk in y.keikat
            ],
        )
        for y in yhteenveto
    ]

    sijoittamatta_vastaus = [
        Sijoittamaton(**s)
        for s in analysoi_sijoittamattomat(tulos.sijoittamatta, tehtavat, kuskit, ajoaika, parametrit)
    ]

    skenaariot_vastaus = (
        [Skenaario(**s) for s in skenaariot_data] if skenaariot_data is not None else None
    )

    vastaus = OptimointiVastaus(
        versio_id=uusi_versio.id,
        versio_nro=uusi_versio.versio_nro,
        kokonaiskustannus_eur=uusi_versio.kokonaiskustannus_eur,
        kuskit=kuskien_ajolistat,
        sijoittamatta=sijoittamatta_vastaus,
        skenaariot=skenaariot_vastaus,
    )
    return json_vastaus(vastaus, rooli, OPTIMOINTIVASTAUS_KUSKILTA_PIILOTETTAVAT)

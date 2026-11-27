from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AjolistaVersio, Kayttaja, KayttajaRooli, Keikka, KeikkaTila, Kuvauspaiva, PaivaKuski
from app.omistus import hae_keikka, hae_versio, on_kuski, rajaa_kuskin_keikat
from app.response_filter import KEIKKA_KUSKILTA_PIILOTETTAVAT, json_vastaus
from app.rooli import kirjautunut_kayttaja, nykyinen_rooli
from app.schemas import KeikanTilaPyynto, KeikkaRead

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


# ---------------------------------------------------------------------------
# N3: kuskin kuittaukset (Tanjan päätös issuessa #38, vaihtoehto A)
# ---------------------------------------------------------------------------

EI_JULKAISTU = "Vain julkaistun ajolistan keikan tilaa voi muuttaa."
EI_TAAKSEPAIN = "Kuittausta ei voi perua. Pyydä koordinaattoria korjaamaan tila."
_JARJESTYS = {KeikkaTila.ODOTTAA: 0, KeikkaTila.KYYDISSA: 1, KeikkaTila.PERILLA: 2}


def _nyt() -> datetime:
    """UTC ilman aikavyöhyketietoa, kuten muutkin aikaleimat kannassa."""
    return datetime.now(UTC).replace(tzinfo=None)


@router.post(
    "/{keikka_id}/tila",
    response_model=KeikkaRead,
    responses={409: {"description": f"{EI_JULKAISTU} / {EI_TAAKSEPAIN}"}},
)
async def aseta_keikan_tila(
    keikka_id: int,
    data: KeikanTilaPyynto,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
    rooli: KayttajaRooli = Depends(nykyinen_rooli),
):
    """Keikan tila: odottaa -> kyydissä -> perillä.

    - KUSKI saa muuttaa vain oman keikkansa tilaa, ja vain eteenpäin
      (myös suoraan perille, esim. tavarakeikka). Toisen kuskin keikka
      näyttää kuskille olemattomalta: 404.
    - KOORDI ja TUOTANTO saavat asettaa minkä tahansa tilan, myös perua.
      Peruttaessa myöhempien tilojen aikaleimat tyhjennetään.
    - Vain julkaistun version keikka (muuten 409).
    - Sama tila uudelleen ei muuta mitään (kaksoisnapautus puhelimessa).
    - Perillä merkitsee keikan myös kuitatuksi, jolloin reoptimointi
      lukitsee sen; perillä-tilasta peruttaessa kuittaus poistuu.
    """
    keikka = await hae_keikka(db, keikka_id, kayttaja, "Keikkaa ei löytynyt")
    if on_kuski(kayttaja):
        paiva_kuski = await db.get(PaivaKuski, keikka.paiva_kuski_id)
        if kayttaja.kuski_id is None or paiva_kuski is None or paiva_kuski.kuski_id != kayttaja.kuski_id:
            raise HTTPException(status_code=404, detail="Keikkaa ei löytynyt")

    versio = await db.get(AjolistaVersio, keikka.versio_id)
    if not versio.julkaistu:
        raise HTTPException(status_code=409, detail=EI_JULKAISTU)

    uusi, vanha = data.tila, keikka.tila
    if uusi != vanha:
        if _JARJESTYS[uusi] < _JARJESTYS[vanha] and on_kuski(kayttaja):
            raise HTTPException(status_code=409, detail=EI_TAAKSEPAIN)
        nyt = _nyt()
        if uusi == KeikkaTila.ODOTTAA:
            keikka.kyydissa_klo = None
            keikka.perilla_klo = None
        elif uusi == KeikkaTila.KYYDISSA:
            keikka.kyydissa_klo = keikka.kyydissa_klo or nyt
            keikka.perilla_klo = None
        else:
            keikka.perilla_klo = nyt
        if uusi == KeikkaTila.PERILLA:
            keikka.kuitattu = True
        elif vanha == KeikkaTila.PERILLA:
            keikka.kuitattu = False
        keikka.tila = uusi
        await db.commit()
        await db.refresh(keikka)

    return json_vastaus(KeikkaRead.model_validate(keikka), rooli, KEIKKA_KUSKILTA_PIILOTETTAVAT)

"""Excel-tuonti rekisteriin (ROADMAP O1).

Kaksi vaihetta, molemmat saavat saman xlsx-tiedoston pyynnön runkona
(ei multipart-lomaketta, joka vaatisi uuden riippuvuuden):

1. `POST /tuotannot/{id}/tuonti/esikatselu` tulkitsee rivit ja kertoo
   virheet riveittäin. Ei tallenna mitään.
2. `POST /tuotannot/{id}/tuonti` tulkitsee tiedoston uudelleen samalla
   tavalla ja tallentaa kelvolliset rivit yhdessä transaktiossa.
   Virheelliset rivit ohitetaan ja niiden rivinumerot palautetaan.

Tiedosto tulkitaan palvelimella molemmilla kerroilla, joten tallennus ei
luota asiakkaan muokkaamaan esikatseluun.

Osoitteita ei geokoodata tuonnissa: 500 osoitetta veisi Nominatimin
1 kutsu/s -rajalla yli kahdeksan minuuttia yhden HTTP-pyynnön sisällä.
Tuodut henkilöt jäävät koordinaatittomiksi, ja ne täydennetään normaalilla
`POST /tuotannot/{id}/geokoodaa` -joukkoreitillä erissä (tehty juuri
Excel-tuontia varten, docs/tuotekartta.md vaihe E).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Henkilo, Kayttaja
from app.omistus import hae_tuotanto
from app.rooli import kirjautunut_kayttaja
from app.schemas import (
    HenkiloCreate,
    TuontiEsikatselu,
    TuontiRiviVastaus,
    TuontiSarake,
    TuontiTallennus,
)
from app.services.excel_tuonti import TuontiTulos, TuontiVirhe, lue_henkilot, lue_rajattu

router = APIRouter(prefix="/tuotannot", tags=["tuonti"])

XLSX_MEDIATYYPPI = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_TIEDOSTO_RUNKONA = {
    "requestBody": {
        "required": True,
        "description": "xlsx-tiedosto sellaisenaan pyynnön runkona (ei multipart-lomaketta).",
        "content": {XLSX_MEDIATYYPPI: {"schema": {"type": "string", "format": "binary"}}},
    }
}
_VIRHEET = {
    413: {"description": "Tiedosto on liian suuri (yli 2 Mt)"},
    422: {"description": "Tiedosto ei ole xlsx, on rikki, purkautuu liian suureksi, siitä puuttuu "
                         "pakollinen sarake tai siinä on liian monta riviä"},
}


async def _lue_ja_tulkitse(request: Request) -> TuontiTulos:
    try:
        sisalto = await lue_rajattu(request.stream())
        return lue_henkilot(sisalto)
    except TuontiVirhe as e:
        raise HTTPException(status_code=e.status, detail=e.viesti) from None


def _avain(nimi: str) -> str:
    return " ".join(nimi.split()).casefold()


@router.post(
    "/{tuotanto_id}/tuonti/esikatselu",
    response_model=TuontiEsikatselu,
    openapi_extra=_TIEDOSTO_RUNKONA,
    responses=_VIRHEET,
)
async def esikatsele_tuonti(
    tuotanto_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    await hae_tuotanto(db, tuotanto_id, kayttaja)
    tulos = await _lue_ja_tulkitse(request)

    # Varoitus (ei virhe) samannimisistä: rekisterissä jo oleva tai sama
    # nimi tiedostossa kahdesti. Kaimoja on oikeasti, joten ei estetä.
    olemassa = {
        _avain(n) for n in (await db.execute(
            select(Henkilo.nimi).where(Henkilo.tuotanto_id == tuotanto_id, Henkilo.aktiivinen.is_(True))
        )).scalars()
    }
    nahdyt: dict[str, int] = {}
    for rivi in tulos.rivit:
        if rivi.henkilo is None:
            continue
        avain = _avain(rivi.henkilo.nimi)
        if avain in olemassa:
            rivi.varoitukset.append("Rekisterissä on jo samanniminen henkilö.")
        if avain in nahdyt:
            rivi.varoitukset.append(f"Sama nimi on myös rivillä {nahdyt[avain]}.")
        else:
            nahdyt[avain] = rivi.rivi

    kelvollisia = sum(1 for r in tulos.rivit if r.henkilo is not None)
    return TuontiEsikatselu(
        sarakkeet=[TuontiSarake(otsikko=o, kentta=k) for o, k in tulos.sarakkeet],
        rivit=[
            TuontiRiviVastaus(rivi=r.rivi, henkilo=r.henkilo, virheet=r.virheet, varoitukset=r.varoitukset)
            for r in tulos.rivit
        ],
        kelvollisia=kelvollisia,
        virheellisia=len(tulos.rivit) - kelvollisia,
    )


@router.post(
    "/{tuotanto_id}/tuonti",
    response_model=TuontiTallennus,
    status_code=201,
    openapi_extra=_TIEDOSTO_RUNKONA,
    responses=_VIRHEET,
)
async def tallenna_tuonti(
    tuotanto_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    kayttaja: Kayttaja = Depends(kirjautunut_kayttaja),
):
    await hae_tuotanto(db, tuotanto_id, kayttaja)
    tulos = await _lue_ja_tulkitse(request)

    tallennettu = 0
    geokoodaamatta = 0
    ohitetut: list[int] = []
    for rivi in tulos.rivit:
        if rivi.henkilo is None:
            ohitetut.append(rivi.rivi)
            continue
        # Sama validointi kuin POST /henkilot (HenkiloCreate).
        data = HenkiloCreate(tuotanto_id=tuotanto_id, **rivi.henkilo.model_dump())
        db.add(Henkilo(**data.model_dump()))
        tallennettu += 1
        if data.osoite:
            geokoodaamatta += 1

    await db.commit()
    return TuontiTallennus(tallennettu=tallennettu, ohitetut_rivit=ohitetut, geokoodaamatta=geokoodaamatta)

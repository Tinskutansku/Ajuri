"""Kirjautuminen: POST /auth/kirjaudu, GET /auth/mina ja demotila
(GET /auth/demo, POST /auth/demo).

Tokenin tarkistus (`kirjautunut_kayttaja`) on `app/rooli.py`:ssä, koska
kaikki muutkin reitit käyttävät sitä (ROADMAP K2).
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    hashaa_salasana,
    luo_token,
    tarkista_salasana,
    tarvitseeko_uudelleenhashin,
)
from app.config import settings
from app.database import get_db
from app.models import Kayttaja, KayttajaRooli
from app.rajoitukset import asiakkaan_ip, limiter, raja_kirjautuminen
from app.rooli import kirjautunut_kayttaja
from app.schemas import (
    DemoKirjautumisPyynto,
    DemoTila,
    KayttajaRead,
    KirjautumisPyynto,
    TokenVastaus,
)
from app.seed import DEMOKAYTTAJAT

router = APIRouter(prefix="/auth", tags=["kirjautuminen"])

# Sama viesti kaikille epäonnistumisille: ei paljasteta, oliko email
# tuntematon, salasana väärä vai käyttäjä passivoitu.
VAARA_TUNNUS = "Väärä sähköposti tai salasana."


@router.post("/kirjaudu", response_model=TokenVastaus)
# IP-osoitteen mukaan, onnistuneet ja epäonnistuneet yhteensä (ROADMAP L2).
@limiter.limit(raja_kirjautuminen, key_func=asiakkaan_ip)
async def kirjaudu(
    request: Request,  # slowapi tarvitsee pyynnön
    pyynto: KirjautumisPyynto,
    db: AsyncSession = Depends(get_db),
):
    email = pyynto.email.strip().lower()
    kayttaja = (
        await db.execute(select(Kayttaja).where(func.lower(Kayttaja.email) == email))
    ).scalar_one_or_none()

    # Salasana tarkistetaan aina (myös tuntemattomalle emailille), jotta
    # vastausaika ei paljasta, onko tunnus olemassa.
    oikein = tarkista_salasana(kayttaja.salasana_hash if kayttaja else None, pyynto.salasana)
    if kayttaja is None or not oikein or not kayttaja.aktiivinen:
        raise HTTPException(status_code=401, detail=VAARA_TUNNUS)

    if tarvitseeko_uudelleenhashin(kayttaja.salasana_hash):
        kayttaja.salasana_hash = hashaa_salasana(pyynto.salasana)
    return await _token_vastaus(db, kayttaja)


async def _token_vastaus(db: AsyncSession, kayttaja: Kayttaja) -> TokenVastaus:
    """Onnistunut kirjautuminen: aikaleima talteen ja token."""
    # Tietokannan DateTime-sarakkeet ovat aikavyöhykkeettömiä: UTC ilman tzinfoa.
    kayttaja.viimeksi_kirjautunut = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(kayttaja)

    return TokenVastaus(
        access_token=luo_token(kayttaja),
        voimassa_s=settings.jwt_voimassa_h * 3600,
        kayttaja=KayttajaRead.model_validate(kayttaja),
    )


@router.get("/mina", response_model=KayttajaRead)
async def mina(kayttaja: Kayttaja = Depends(kirjautunut_kayttaja)):
    return kayttaja


# ---------------------------------------------------------------------------
# Demotila (ROADMAP M2)
# ---------------------------------------------------------------------------

# Roolit, joilla demoon pääsee napista. Koordinaattori näkee saman kuin
# tuotanto (paitsi tuotannon asetukset), joten nappeja on kaksi.
DEMOROOLIT = (KayttajaRooli.TUOTANTO, KayttajaRooli.KUSKI)
# Seedin demokäyttäjien emailit roolin mukaan (app/seed.py, DEMOKAYTTAJAT).
_DEMO_EMAILIT = {rooli: email for email, _nimi, rooli, _salasana in DEMOKAYTTAJAT}

DEMO_EI_KAYTOSSA = "Demotila ei ole käytössä."
DEMODATAA_EI_OLE = "Demodataa ei ole vielä luotu. Aja seed (AJURI_SEED=true)."


async def _demokayttaja(db: AsyncSession, rooli: KayttajaRooli) -> Kayttaja | None:
    kayttaja = (
        await db.execute(select(Kayttaja).where(Kayttaja.email == _DEMO_EMAILIT[rooli]))
    ).scalar_one_or_none()
    return kayttaja if kayttaja is not None and kayttaja.aktiivinen else None


@router.get("/demo", response_model=DemoTila)
async def demo_tila(db: AsyncSession = Depends(get_db)):
    """Avoin reitti: kirjautumissivu kysyy tästä, näytetäänkö demonapit.
    Roolit, joiden demokäyttäjää ei ole kannassa (seed ajamatta), jätetään
    pois, jotta napit eivät johda virheeseen."""
    if not settings.demo:
        return DemoTila(kaytossa=False, roolit=[])
    roolit = [r for r in DEMOROOLIT if await _demokayttaja(db, r) is not None]
    return DemoTila(kaytossa=bool(roolit), roolit=roolit)


@router.post("/demo", response_model=TokenVastaus)
# Sama IP-kohtainen raja kuin tavallisella kirjautumisella (oma laskuri).
@limiter.limit(raja_kirjautuminen, key_func=asiakkaan_ip)
async def demokirjautuminen(
    request: Request,  # slowapi tarvitsee pyynnön
    pyynto: DemoKirjautumisPyynto,
    db: AsyncSession = Depends(get_db),
):
    """Kirjautuu seedin demokäyttäjäksi ilman salasanaa. Vain kun DEMO=true;
    muuten 404, kuin reittiä ei olisi."""
    if not settings.demo:
        raise HTTPException(status_code=404, detail=DEMO_EI_KAYTOSSA)
    kayttaja = await _demokayttaja(db, pyynto.rooli)
    if kayttaja is None:
        raise HTTPException(status_code=503, detail=DEMODATAA_EI_OLE)
    return await _token_vastaus(db, kayttaja)

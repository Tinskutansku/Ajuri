"""Osoitteiden geokoodausvälimuisti (docs/tuotekartta.md, vaihe E):
kysyy ensin Geokoodi-taulusta, hakee puuttuvan geokooderilta ja
tallentaa tuloksen — myös epäonnistuneen haun, jotta samaa toimimatonta
osoitetta ei kysytä uudestaan. Verkkovirheitä EI cachetta (voi olla
tilapäinen), vain geokooderin normaalisti palauttaman "ei löytynyt".
Negatiivinen osuma vanhenee (settings.geokoodaus_negatiivinen_ttl_pv),
positiivinen ei koskaan.

Ei committaa - jättää sen kutsujan (reititin / joukkoendpoint) vastuulle,
jotta tämä pysyy osana samaa transaktiota eikä committaa kutsujan muita
kesken olevia muutoksia ennenaikaisesti."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Geokoodi
from app.services.geocoder_client import GeocoderClient

logger = logging.getLogger(__name__)


def vertailuavain(osoite: str | None) -> str | None:
    """Normalisoitu muoto VERTAILUUN (esim. "muuttuiko osoite" PUT:issa)
    - EI pituusrajaa. Isot/pienet kirjaimet ja ylimääräiset välilyönnit
    eivät saa tuottaa kahta eri riviä/eri näköistä osoitetta."""
    if osoite is None:
        return None
    normalisoitu = " ".join(osoite.split()).casefold()
    return normalisoitu or None


def normalisoi_avain(osoite: str | None) -> str | None:
    """VÄLIMUISTIN AVAIN (Geokoodi.osoite-sarake) - sama normalisointi
    kuin vertailuavain, mutta palauttaa None jos tulos ylittää
    sarakkeen leveyden (300) niin ettei INSERT kaadu liian pitkään
    osoitteeseen. EI KÄYTETÄ vertailuun (kaksi ERI yli-300-merkkistä
    osoitetta molemmat normalisoituisivat None:ksi ja näyttäisivät
    vertailussa samalta) - vertailuun käytä vertailuavain():ia."""
    avain = vertailuavain(osoite)
    if avain is None or len(avain) > 300:
        return None
    return avain


def _nyt() -> datetime:
    """Yksi yhtenäinen aikaperusta kaikille Geokoodi.haettu-kirjoituksille
    ja TTL-vertailuille - EI sekoiteta DB:n server_default now():ia ja
    Python-puolen kelloa samassa vertailussa (migraation
    server_default=text('now()') on vain turvaverkko INSERTille, ei
    koskaan sovelluslogiikan lukema)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _tuore(rivi: Geokoodi) -> bool:
    if rivi.lat is not None:
        return True  # positiivinen osuma ei vanhene koskaan
    return _nyt() - rivi.haettu <= timedelta(days=settings.geokoodaus_negatiivinen_ttl_pv)


async def geokoodaa_valimuistilla(
    db: AsyncSession, osoite: str, geocoder: GeocoderClient, lahde: str = "nominatim",
) -> tuple[float, float] | None:
    avain = normalisoi_avain(osoite)
    if not avain:
        return None

    rivi = (await db.execute(select(Geokoodi).where(Geokoodi.osoite == avain))).scalar_one_or_none()
    if rivi is not None and _tuore(rivi):
        return (rivi.lat, rivi.lon) if rivi.lat is not None else None

    try:
        tulos = await geocoder.geokoodaa(osoite)  # ALKUPERÄINEN osoite, avain on vain välimuistin key
    except Exception:
        logger.exception("Geokoodaus epäonnistui osoitteelle %r", osoite)
        return None

    lat, lon = tulos if tulos is not None else (None, None)

    if rivi is not None:
        # Vanhentunut negatiivinen osuma - päivitetään olemassa oleva rivi
        # (ei uutta INSERTiä, osoite on jo UNIQUE-sarakkeessa).
        rivi.lat, rivi.lon, rivi.lahde, rivi.haettu = lat, lon, lahde, _nyt()
        await db.flush()
        return tulos

    # Kilpailutilanne: kaksi samanaikaista pyyntöä samalla UUDELLA
    # osoitteella voi törmätä UniqueConstraint('osoite')-rajoitteeseen.
    # SAVEPOINTin sisällä epäonnistuva INSERT ei peru kutsujan istunnon
    # muita kesken olevia muutoksia (esim. Henkilo-riviä joka ollaan
    # samalla parhaillaan tallentamassa) - vain tämän lisäyksen.
    # (VAHVISTETTU VAIHEESSA 0 toimivaksi myös testien SQLite-enginellä.)
    try:
        async with db.begin_nested():
            db.add(Geokoodi(osoite=avain, lat=lat, lon=lon, lahde=lahde, haettu=_nyt()))
            await db.flush()
    except IntegrityError:
        # Kilpaileva transaktio ehti ensin. scalar_one_or_none(), EI
        # scalar_one(): jos rivi ei vielä (isolaatiotason takia) näy
        # tälle transaktiolle, älä kaadu NoResultFoundiin - palauta
        # mieluummin juuri itse laskettu tulos kuin räjäytä koko tallennus.
        kilpaileva = (
            await db.execute(select(Geokoodi).where(Geokoodi.osoite == avain))
        ).scalar_one_or_none()
        if kilpaileva is None:
            return tulos
        return (kilpaileva.lat, kilpaileva.lon) if kilpaileva.lat is not None else None

    return tulos


async def on_tuore_kielteinen_osuma(db: AsyncSession, osoite: str) -> bool:
    """True jos osoitteella on jo tuore (ei vanhentunut) negatiivinen
    Geokoodi-osuma - turha käyttää joukkoendpointin eräbudjettia siihen
    uudestaan juuri nyt (ks. app/routers/tuotanto.py, 'jaljella')."""
    avain = normalisoi_avain(osoite)
    if not avain:
        return False
    rivi = (await db.execute(select(Geokoodi).where(Geokoodi.osoite == avain))).scalar_one_or_none()
    return rivi is not None and rivi.lat is None and _tuore(rivi)


async def taydenna_koordinaatit(
    db: AsyncSession, geocoder: GeocoderClient, kohde,
    osoite_kentta: str = "osoite", lat_kentta: str = "lat", lon_kentta: str = "lon",
) -> None:
    """Täyttää kohteen lat/lon-kentät osoitteesta JOS osoite on annettu
    JA kumpikaan koordinaatti ei ole jo asetettu (ei ylikirjoita käsin
    syötettyjä koordinaatteja). Käytetään POST:ssa, joukkoendpointissa
    ja PUT:in "osoite muuttui" -haarassa (ks. paivita_koordinaatit_put)."""
    osoite = getattr(kohde, osoite_kentta)
    if not osoite or getattr(kohde, lat_kentta) is not None or getattr(kohde, lon_kentta) is not None:
        return
    tulos = await geokoodaa_valimuistilla(db, osoite, geocoder)
    if tulos is not None:
        setattr(kohde, lat_kentta, tulos[0])
        setattr(kohde, lon_kentta, tulos[1])


async def paivita_koordinaatit_put(
    db: AsyncSession, geocoder: GeocoderClient, kohde, annetut_kentat: set[str],
    edellinen_osoite: str | None, edellinen_lat: float | None, edellinen_lon: float | None,
    osoite_kentta: str = "osoite", lat_kentta: str = "lat", lon_kentta: str = "lon",
) -> None:
    """PUT-päivityksen koordinaattilogiikka, kolme tapausta:
    1) lat/lon annettu pyynnössä eksplisiittisesti -> käsin annettu voittaa,
       jo asetettu geneerisellä setattr-silmukalla, ei koskea.
    2) osoite muuttui eikä koordinaatteja annettu -> nollaa vanhat ja
       geokoodaa uudet.
    3) osoite ei muuttunut eikä koordinaatteja annettu -> säilytä vanhat
       koordinaatit koskemattomina (muuten geneerinen "täysi korvaus"
       -setattr-silmukka olisi jo hiljaa nollannut ne, koska Create-
       skeeman lat/lon-oletusarvo on None kun kenttä puuttuu pyynnöstä)."""
    if lat_kentta in annetut_kentat or lon_kentta in annetut_kentat:
        return

    uusi_osoite = getattr(kohde, osoite_kentta)
    # vertailuavain(), EI normalisoi_avain(): kaksi ERI yli-300-merkkistä
    # osoitetta eivät saa näyttää samalta vain koska molemmat
    # normalisoi_avain() palauttaisi niille None:n.
    if vertailuavain(uusi_osoite) != vertailuavain(edellinen_osoite):
        setattr(kohde, lat_kentta, None)
        setattr(kohde, lon_kentta, None)
        await taydenna_koordinaatit(db, geocoder, kohde, osoite_kentta, lat_kentta, lon_kentta)
    else:
        setattr(kohde, lat_kentta, edellinen_lat)
        setattr(kohde, lon_kentta, edellinen_lon)

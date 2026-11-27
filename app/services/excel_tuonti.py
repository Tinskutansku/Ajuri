"""Excel-tuonti rekisteriin (ROADMAP O1, docs/tuotekartta.md V2 #2).

Lukee xlsx-tiedoston henkilöriveiksi. Ei koske tietokantaan eikä verkkoon:
reititin (`app/routers/tuonti.py`) tallentaa tulkitut rivit.

Tiedostoon ei luoteta. Tarkistukset tehdään tässä järjestyksessä, ja
openpyxl avaa tiedoston vasta kun kaikki ovat menneet läpi:

1. Koko (reititin lukee enintään `TIEDOSTO_MAX_TAVUA`, ks. `lue_rajattu`).
2. Todellinen tyyppi sisällöstä, ei päätteestä: zip-rakenne,
   `[Content_Types].xml` ja siinä taulukkolaskentakirjan sisältötyyppi.
3. Zip-pommi: tiedostomäärä ja purettu kokonaiskoko rajattu. Pythonin
   `zipfile` ei pura otsakkeessa ilmoitettua kokoa enempää, joten
   ilmoitettujen kokojen summa on todellinen yläraja myös openpyxl:lle.
4. XML-pommi ja ulkoiset entiteetit: oikeassa xlsx:ssä ei ole koskaan
   DTD:tä, joten `<!DOCTYPE` tai `<!ENTITY` missä tahansa XML-osassa
   hylkää tiedoston. Tämä korvaa defusedxml-kirjaston (uusi riippuvuus).

Kaavoja ei suoriteta: `data_only=True` lukee vain Excelin tallentaman
arvon. Teksti tallennetaan tekstinä. Jos joskus tehdään Excel- tai
CSV-vienti, `=`, `+`, `-` ja `@` -alkuiset solut pitää silloin escapettaa
(kaava-injektio), koska tuonti ei muuta niitä.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, time

from pydantic import ValidationError

from app.models import HenkiloTyyppi
from app.schemas import HenkiloTuontiRivi

TIEDOSTO_MAX_TAVUA = 2 * 1024 * 1024          # 2 Mt
RIVIT_MAX = 500                              # datarivejä, otsikkoa ei lasketa
PURETTU_MAX_TAVUA = 20 * 1024 * 1024         # zip-pommiraja: purettu kokonaiskoko
ZIP_TIEDOSTOT_MAX = 200                      # tavallisessa xlsx:ssä on ~10-20 osaa
SARAKKEET_MAX = 50                           # luetaan vain näin monta saraketta
OTSIKKORIVI_HAKU = 10                        # otsikko etsitään näin monelta ensimmäiseltä riviltä

XLSX_SISALTOTYYPPI = b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
XLSM_SISALTOTYYPPI = b"application/vnd.ms-excel.sheet.macroEnabled.main+xml"

# DTD-merkinnät kaikissa koodauksissa, jotka XML-jäsennin tunnistaa itse
# (UTF-16-koodattu osa ohittaisi pelkän UTF-8-haun).
_KIELLETYT_XML = tuple(
    merkki.encode(koodaus)
    for merkki in ("<!DOCTYPE", "<!ENTITY")
    for koodaus in ("utf-8", "utf-16-le", "utf-16-be")
)

# Otsikko (pienillä kirjaimilla, välilyönnit siivottuna) -> HenkiloTuontiRivi-kenttä.
SARAKEALIAKSET: dict[str, str] = {
    "nimi": "nimi", "name": "nimi", "henkilö": "nimi", "henkilo": "nimi",
    "tyyppi": "tyyppi", "type": "tyyppi", "cast/crew": "tyyppi", "ryhmä": "tyyppi", "ryhma": "tyyppi",
    "rooli": "roolinimi", "roolinimi": "roolinimi", "role": "roolinimi", "character": "roolinimi",
    "titteli": "titteli", "tehtävä": "titteli", "tehtava": "titteli", "title": "titteli",
    "position": "titteli", "osasto/titteli": "titteli",
    "puhelin": "puhelin", "puh": "puhelin", "puh.": "puhelin", "puhelinnumero": "puhelin",
    "phone": "puhelin", "gsm": "puhelin",
    "osoite": "osoite", "nouto-osoite": "osoite", "noutoosoite": "osoite", "address": "osoite",
    "huomiot": "huomiot", "huomio": "huomiot", "lisätiedot": "huomiot", "lisatiedot": "huomiot",
    "notes": "huomiot",
}
PAKOLLISET_SARAKKEET = ("nimi",)

TYYPPIALIAKSET: dict[str, HenkiloTyyppi] = {
    "cast": HenkiloTyyppi.CAST, "näyttelijä": HenkiloTyyppi.CAST, "nayttelija": HenkiloTyyppi.CAST,
    "crew": HenkiloTyyppi.CREW, "työryhmä": HenkiloTyyppi.CREW, "tyoryhma": HenkiloTyyppi.CREW,
}


class TuontiVirhe(Exception):
    """Koko tiedosto hylätään. `status` on HTTP-statuskoodi."""

    def __init__(self, viesti: str, status: int = 422) -> None:
        super().__init__(viesti)
        self.viesti = viesti
        self.status = status


@dataclass
class TulkittuRivi:
    rivi: int                                    # Excelin rivinumero (1 = ensimmäinen rivi)
    henkilo: HenkiloTuontiRivi | None            # None jos rivillä on virheitä
    virheet: list[str] = field(default_factory=list)
    varoitukset: list[str] = field(default_factory=list)


@dataclass
class TuontiTulos:
    sarakkeet: list[tuple[str, str | None]]      # (otsikko tiedostossa, kenttä tai None = ei käytetä)
    rivit: list[TulkittuRivi]


# ---------------------------------------------------------------------------
# Tiedoston tarkistus ennen openpyxl:ää
# ---------------------------------------------------------------------------


def tarkista_xlsx(sisalto: bytes) -> None:
    """Hylkää muun kuin taulukkolaskentakirjan, zip-pommin ja XML-pommin."""
    if len(sisalto) > TIEDOSTO_MAX_TAVUA:
        raise TuontiVirhe(f"Tiedosto on liian suuri (enintään {TIEDOSTO_MAX_TAVUA // (1024 * 1024)} Mt).", 413)
    if not sisalto:
        raise TuontiVirhe("Tiedosto on tyhjä.")
    # Zip alkaa aina paikallisen tiedosto-otsakkeen tunnisteella.
    if not sisalto.startswith(b"PK\x03\x04"):
        raise TuontiVirhe("Tiedosto ei ole Excel-tiedosto (xlsx).")
    try:
        with zipfile.ZipFile(io.BytesIO(sisalto)) as zf:
            osat = zf.infolist()
            if len(osat) > ZIP_TIEDOSTOT_MAX:
                raise TuontiVirhe("Tiedostossa on liian monta osaa. Tallenna se Excelissä uudelleen.")
            if sum(o.file_size for o in osat) > PURETTU_MAX_TAVUA:
                raise TuontiVirhe("Tiedosto on purettuna liian suuri.")
            nimet = {o.filename for o in osat}
            if "[Content_Types].xml" not in nimet:
                raise TuontiVirhe("Tiedosto ei ole Excel-tiedosto (xlsx).")
            sisaltotyypit = zf.read("[Content_Types].xml")
            if XLSX_SISALTOTYYPPI not in sisaltotyypit and XLSM_SISALTOTYYPPI not in sisaltotyypit:
                raise TuontiVirhe("Tiedosto ei ole Excel-taulukko (xlsx).")
            for osa in osat:
                if osa.filename.endswith((".xml", ".rels", ".vml")):
                    data = zf.read(osa)
                    if any(m in data for m in _KIELLETYT_XML):
                        raise TuontiVirhe("Tiedostossa on kiellettyjä XML-määrittelyjä.")
    except TuontiVirhe:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, RuntimeError, OSError, EOFError):
        # NotImplementedError: tuntematon pakkaustapa, RuntimeError: salattu zip
        raise TuontiVirhe("Tiedosto on rikki tai ei ole Excel-tiedosto (xlsx).") from None


# ---------------------------------------------------------------------------
# Lukeminen ja tulkinta
# ---------------------------------------------------------------------------


def _avain(otsikko: object) -> str:
    return " ".join(str(otsikko).split()).casefold() if otsikko is not None else ""


def _tekstiksi(arvo: object) -> str | None:
    """Solun arvo tekstinä. Excel tallentaa puhelinnumeron usein lukuna:
    401234567.0 -> "401234567" (alkunolla on jo kadonnut Excelissä)."""
    if arvo is None:
        return None
    if isinstance(arvo, bool):
        teksti = "kyllä" if arvo else "ei"
    elif isinstance(arvo, float) and arvo.is_integer():
        teksti = str(int(arvo))
    elif isinstance(arvo, datetime | date | time):
        teksti = arvo.isoformat()
    else:
        teksti = str(arvo)
    teksti = teksti.strip()
    return teksti or None


def _avaa_tyokirja(sisalto: bytes):
    # Tuodaan vasta käytössä: openpyxl on raskas eikä sitä tarvita muualla.
    from openpyxl import load_workbook

    try:
        return load_workbook(io.BytesIO(sisalto), read_only=True, data_only=True, keep_links=False)
    except Exception:
        # openpyxl heittää rikkinäisestä sisällöstä hyvin monenlaisia
        # poikkeuksia (KeyError, ValueError, XML-virheet...).
        raise TuontiVirhe("Tiedosto on rikki tai ei ole Excel-tiedosto (xlsx).") from None


def lue_henkilot(sisalto: bytes) -> TuontiTulos:
    """Tarkistaa tiedoston ja tulkitsee ensimmäisen välilehden henkilöiksi.

    Otsikkorivi on ensimmäinen ei-tyhjä rivi. Tyhjät rivit ohitetaan.
    Rivikohtaiset ongelmat palautetaan rivin virheinä; koko tiedoston
    ongelmat (tyyppi, koko, puuttuva pakollinen sarake, liikaa rivejä)
    heittävät `TuontiVirhe`n.
    """
    tarkista_xlsx(sisalto)
    kirja = _avaa_tyokirja(sisalto)
    try:
        lehti = kirja.worksheets[0] if kirja.worksheets else None
        if lehti is None:
            raise TuontiVirhe("Tiedostossa ei ole yhtään välilehteä.")
        try:
            rivit_iter = lehti.iter_rows(max_col=SARAKKEET_MAX, values_only=True)
            return _tulkitse(rivit_iter)
        except TuontiVirhe:
            raise
        except Exception:
            raise TuontiVirhe("Tiedosto on rikki tai ei ole Excel-tiedosto (xlsx).") from None
    finally:
        kirja.close()


def _tulkitse(rivit_iter) -> TuontiTulos:
    otsikot: list[str] | None = None
    kentat: list[str | None] = []
    tulos_rivit: list[TulkittuRivi] = []

    for rivinro, solut in enumerate(rivit_iter, start=1):
        arvot = [_tekstiksi(s) for s in solut]
        if not any(arvot):
            continue

        if otsikot is None:
            if rivinro > OTSIKKORIVI_HAKU:
                break
            # iter_rows täydentää rivin SARAKKEET_MAX-levyiseksi: loppupään
            # tyhjät otsikot pois.
            while arvot and arvot[-1] is None:
                arvot.pop()
            otsikot = [a or "" for a in arvot]
            kentat = _tunnista_sarakkeet(otsikot)
            continue

        if len(tulos_rivit) >= RIVIT_MAX:
            raise TuontiVirhe(f"Tiedostossa on liian monta riviä (enintään {RIVIT_MAX}).")
        tulos_rivit.append(_tulkitse_rivi(rivinro, arvot, kentat))

    if otsikot is None:
        raise TuontiVirhe("Tiedostosta ei löytynyt otsikkoriviä.")
    puuttuvat = [k for k in PAKOLLISET_SARAKKEET if k not in kentat]
    if puuttuvat:
        loydetyt = ", ".join(o for o in otsikot if o) or "ei yhtään"
        raise TuontiVirhe(
            f"Pakollinen sarake puuttuu: {', '.join(puuttuvat)}. Tiedostosta löytyi: {loydetyt}."
        )

    return TuontiTulos(sarakkeet=list(zip(otsikot, kentat, strict=False)), rivit=tulos_rivit)


def _tunnista_sarakkeet(otsikot: list[str]) -> list[str | None]:
    """Otsikot kentiksi. Sama kenttä kahdesti -> vain ensimmäinen käytetään."""
    kaytetyt: set[str] = set()
    kentat: list[str | None] = []
    for otsikko in otsikot:
        kentta = SARAKEALIAKSET.get(_avain(otsikko))
        if kentta in kaytetyt:
            kentta = None
        if kentta:
            kaytetyt.add(kentta)
        kentat.append(kentta)
    return kentat


def _tulkitse_rivi(rivinro: int, arvot: list[str | None], kentat: list[str | None]) -> TulkittuRivi:
    data: dict[str, str | None] = {}
    for kentta, arvo in zip(kentat, arvot, strict=False):
        if kentta and arvo is not None:
            data[kentta] = arvo

    virheet: list[str] = []
    varoitukset: list[str] = []

    tyyppi_teksti = data.pop("tyyppi", None)
    if tyyppi_teksti is None:
        # Ei tyyppiä: roolinimi tarkoittaa näyttelijää, muuten työryhmä.
        tyyppi = HenkiloTyyppi.CAST if data.get("roolinimi") else HenkiloTyyppi.CREW
        varoitukset.append(f"Tyyppi puuttui, tulkittu: {tyyppi.value}.")
    else:
        tyyppi = TYYPPIALIAKSET.get(_avain(tyyppi_teksti))
        if tyyppi is None:
            virheet.append(f"Tuntematon tyyppi \"{tyyppi_teksti[:50]}\" (sallitut: cast, crew).")

    if not data.get("nimi"):
        virheet.append("Nimi puuttuu.")

    if virheet:
        return TulkittuRivi(rivi=rivinro, henkilo=None, virheet=virheet)

    try:
        henkilo = HenkiloTuontiRivi(tyyppi=tyyppi, **data)
    except ValidationError as e:
        for virhe in e.errors():
            kentta = ".".join(str(p) for p in virhe["loc"])
            virheet.append(f"{kentta}: {_virheteksti(virhe)}")
        return TulkittuRivi(rivi=rivinro, henkilo=None, virheet=virheet)

    return TulkittuRivi(rivi=rivinro, henkilo=henkilo, varoitukset=varoitukset)


def _virheteksti(virhe: dict) -> str:
    if virhe["type"] == "string_too_long":
        return f"liian pitkä (enintään {virhe['ctx']['max_length']} merkkiä)"
    return str(virhe["msg"])


async def lue_rajattu(stream, raja: int = TIEDOSTO_MAX_TAVUA) -> bytes:
    """Lukee pyynnön rungon, mutta lopettaa heti kun raja ylittyy, jottei
    iso lähetys täytä muistia ennen kokotarkistusta."""
    puskuri = bytearray()
    async for pala in stream:
        puskuri.extend(pala)
        if len(puskuri) > raja:
            raise TuontiVirhe(f"Tiedosto on liian suuri (enintään {raja // (1024 * 1024)} Mt).", 413)
    return bytes(puskuri)

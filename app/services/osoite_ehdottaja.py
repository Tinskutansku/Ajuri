"""Osoite-ehdotukset kirjoittaessa (automaattitäydennys).

Oma abstraktio GeocoderClientin rinnalla, koska Nominatimin käyttöehdot
kieltävät nimenomaan automaattitäydennyksen ("Auto-complete search ...
you must not implement such a service on the client side using the API",
https://operations.osmfoundation.org/policies/nominatim/). Photon
(https://photon.komoot.io) käyttää samaa OpenStreetMap-dataa ja on tehty
search-as-you-type-käyttöön. Tanja hyväksyi Photonin 6.11.2026.

Geokoodaus (osoite -> koordinaatit tallennettaessa) pysyy Nominatimissa
GeocoderClientin takana; tämä moduuli vain ehdottaa osoitteita, ja
valitun ehdotuksen koordinaatit lähetetään tallennuksessa mukana."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
import time

import httpx

from app.config import settings


@dataclass(frozen=True)
class Ehdotus:
    nimi: str
    lat: float
    lon: float


class OsoiteEhdottaja(ABC):
    @abstractmethod
    async def ehdota(self, q: str, raja: int = 5) -> list[Ehdotus]:
        """Palauttaa enintään `raja` osoite-ehdotusta hakutekstille.
        Tyhjä lista = ei osumia. Voi heittää httpx.HTTPError-poikkeuksen
        verkko-/palveluvirheestä."""


def muotoile_photon(props: dict) -> str:
    """Photonin GeoJSON-propertiesista luettava rivi, esim.
    "Humalistonkatu 1, 00250 Helsinki" tai
    "Kansallisteatteri, Läntinen Teatterikuja 1, 00100 Helsinki"."""
    katu = props.get("street")
    numero = props.get("housenumber")
    nimi = props.get("name")
    katuosoite = " ".join(x for x in (katu, numero) if x) or None

    osat: list[str] = []
    if nimi and nimi != katu:
        osat.append(nimi)
    if katuosoite:
        osat.append(katuosoite)
    elif nimi and not osat:
        osat.append(nimi)

    paikka = " ".join(
        x for x in (props.get("postcode"), props.get("city") or props.get("district") or props.get("county")) if x
    )
    if paikka and paikka not in osat:
        osat.append(paikka)

    maa = props.get("country")
    if maa and props.get("countrycode", "").upper() != "FI":
        osat.append(maa)

    return ", ".join(osat)


class PhotonEhdottaja(OsoiteEhdottaja):
    """Photon-haku pienellä muistivälimuistilla: sama hakuteksti (esim.
    kun käyttäjä pyyhkii merkin ja kirjoittaa sen uudelleen) ei mene
    Photonille toista kertaa. Frontti debouncettaa lisäksi."""

    _VALIMUISTI_KOKO = 256
    _VALIMUISTI_TTL_S = 3600

    def __init__(
        self,
        base_url: str | None = None,
        user_agent: str | None = None,
        bias: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (base_url or settings.photon_base_url).rstrip("/")
        self._user_agent = user_agent or settings.nominatim_user_agent
        self._bias = settings.photon_bias if bias is None else bias
        self._transport = transport  # testeille: httpx.MockTransport
        self._valimuisti: OrderedDict[tuple[str, int], tuple[float, list[Ehdotus]]] = OrderedDict()

    async def ehdota(self, q: str, raja: int = 5) -> list[Ehdotus]:
        avain = (" ".join(q.lower().split()), raja)
        osuma = self._valimuisti.get(avain)
        if osuma and time.monotonic() - osuma[0] < self._VALIMUISTI_TTL_S:
            self._valimuisti.move_to_end(avain)
            return osuma[1]

        # Pyydetään muutama ylimääräinen, koska samannimiset duplikaatit
        # (sama katu useana OSM-kappaleena) karsitaan alla.
        params: dict[str, str | int] = {"q": q, "limit": min(raja * 2, 20)}
        if self._bias:
            lat, lon = self._bias.split(",")
            params["lat"], params["lon"] = lat.strip(), lon.strip()

        async with httpx.AsyncClient(timeout=8.0, transport=self._transport) as client:
            vastaus = await client.get(
                f"{self._base_url}/api/",
                params=params,
                headers={"User-Agent": self._user_agent},
            )
            vastaus.raise_for_status()

        tulokset: list[Ehdotus] = []
        nahdyt: set[str] = set()
        for f in vastaus.json().get("features", []):
            try:
                lon_, lat_ = f["geometry"]["coordinates"][:2]
            except (KeyError, TypeError, ValueError):
                continue
            nimi = muotoile_photon(f.get("properties") or {})
            if not nimi or nimi in nahdyt:
                continue
            nahdyt.add(nimi)
            tulokset.append(Ehdotus(nimi=nimi, lat=float(lat_), lon=float(lon_)))
            if len(tulokset) >= raja:
                break

        self._valimuisti[avain] = (time.monotonic(), tulokset)
        if len(self._valimuisti) > self._VALIMUISTI_KOKO:
            self._valimuisti.popitem(last=False)
        return tulokset


_ehdottaja: OsoiteEhdottaja | None = None


def get_osoite_ehdottaja() -> OsoiteEhdottaja:
    global _ehdottaja
    if _ehdottaja is None:
        _ehdottaja = PhotonEhdottaja()
    return _ehdottaja

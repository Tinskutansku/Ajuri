"""Geokoodaus-API-abstraktio: GeocoderClient-rajapinnan taakse voi
kytkeä minkä tahansa geokoodauspalvelun (Nominatim, Google Geocoding,
Mapbox) muuttamatta kutsuvaa koodia."""

from abc import ABC, abstractmethod
import asyncio
import time

import httpx

from app.config import settings


class GeocoderClient(ABC):
    @abstractmethod
    async def geokoodaa(self, osoite: str) -> tuple[float, float] | None:
        """Palauttaa (lat, lon) annetulle osoitteelle, tai None jos
        osoitetta ei löytynyt. Voi heittää poikkeuksen verkko-/palveluvirheestä."""


class NominatimGeocoder(GeocoderClient):
    """Nominatim-käyttöehdot: yksilöivä User-Agent JA enintään 1 kutsu/s
    (https://operations.osmfoundation.org/policies/nominatim/). Lukko +
    edellisen kutsun aikaleima pakottavat väliksi tässä instanssissa,
    joka on moduulitason singleton (ks. get_geocoder_client) - kaikki
    kutsut koko sovelluksessa jakavat saman läpisyötteen.

    HUOM (tiedostettu rajoitus, ei korjata nyt): 1 kutsu/s -rajoite
    toteutuu vain YHDEN prosessin sisällä. Jos sovellus ajetaan
    useammalla uvicorn-workerilla (esim. `--workers 4`), jokaisella
    workerilla on oma singleton-instanssinsa eikä rajoite päde koko
    sovellukselle - ylittäisi Nominatimin käyttöehdot moniprosessi-
    ajossa."""

    _MIN_VALI_S = 1.0

    def __init__(
        self, base_url: str | None = None, user_agent: str | None = None,
        countrycodes: str | None = None,
    ) -> None:
        self._base_url = base_url or settings.nominatim_base_url
        self._user_agent = user_agent or settings.nominatim_user_agent
        self._countrycodes = countrycodes if countrycodes is not None else settings.nominatim_countrycodes
        self._lock = asyncio.Lock()
        self._edellinen_kutsu: float | None = None

    async def geokoodaa(self, osoite: str) -> tuple[float, float] | None:
        params = {"q": osoite, "format": "json", "limit": 1}
        if self._countrycodes:
            params["countrycodes"] = self._countrycodes

        async with self._lock:
            if self._edellinen_kutsu is not None:
                odota = self._MIN_VALI_S - (time.monotonic() - self._edellinen_kutsu)
                if odota > 0:
                    await asyncio.sleep(odota)
            async with httpx.AsyncClient(timeout=15.0) as client:
                vastaus = await client.get(
                    f"{self._base_url}/search",
                    params=params,
                    headers={"User-Agent": self._user_agent},
                )
                vastaus.raise_for_status()
            self._edellinen_kutsu = time.monotonic()

        data = vastaus.json()
        if not data:
            return None
        return float(data[0]["lat"]), float(data[0]["lon"])


_geocoder_client: GeocoderClient | None = None


def get_geocoder_client() -> GeocoderClient:
    global _geocoder_client
    if _geocoder_client is None:
        _geocoder_client = NominatimGeocoder()
    return _geocoder_client

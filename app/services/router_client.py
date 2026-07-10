"""Reititys-API-abstraktio: RouterClient-rajapinnan taakse voi kytkeä
minkä tahansa matriisipalvelun (OSRM, OpenRouteService, Google Distance
Matrix) muuttamatta kutsuvaa koodia."""

from abc import ABC, abstractmethod

import httpx

from app.config import settings


class RouterClient(ABC):
    @abstractmethod
    async def matriisi(
        self, pisteet: list[tuple[float, float]]
    ) -> tuple[list[list[int]], list[list[float]]]:
        """Palauttaa (ajoaika_s, matka_m) -matriisit annettujen pisteiden
        välillä yhtenä kutsuna. pisteet on lista (lat, lon) -pareja;
        palautetut NxN-matriisit ovat samassa järjestyksessä (rivi=lähtö,
        sarake=kohde)."""


class OSRMRouterClient(RouterClient):
    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url or settings.osrm_base_url

    async def matriisi(
        self, pisteet: list[tuple[float, float]]
    ) -> tuple[list[list[int]], list[list[float]]]:
        # OSRM käyttää lon,lat-järjestystä koordinaateissa.
        koordinaatit = ";".join(f"{lon},{lat}" for lat, lon in pisteet)
        url = f"{self._base_url}/table/v1/driving/{koordinaatit}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            vastaus = await client.get(url, params={"annotations": "duration,distance"})
            vastaus.raise_for_status()

        data = vastaus.json()
        if data.get("code") != "Ok":
            raise RuntimeError(f"OSRM-virhe: {data.get('code')} {data.get('message', '')}")

        def tarkista(arvo: float | None) -> float:
            if arvo is None:
                raise RuntimeError("OSRM ei löytänyt reittiä kaikkien pisteiden välille")
            return arvo

        kestot = [[round(tarkista(s)) for s in rivi] for rivi in data["durations"]]
        matkat = [[float(tarkista(m)) for m in rivi] for rivi in data["distances"]]
        return kestot, matkat


_router_client: RouterClient | None = None


def get_router_client() -> RouterClient:
    global _router_client
    if _router_client is None:
        _router_client = OSRMRouterClient()
    return _router_client

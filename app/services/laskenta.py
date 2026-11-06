"""Optimoinnin ajo erillisessä prosessissa.

Miksi prosessi eikä säie: OR-Toolsin C++-ratkaisija ei vapauta Pythonin
GIL-lukkoa ratkaisun aikana (SWIG-kääre), ja se kutsuu lisäksi jatkuvasti
Python-callbackeja. Säikeessä ajettuna backendin tapahtumasilmukka sai
GIL:n vain satunnaisesti, ja kevyetkin haut (GET /tuotannot) kestivät yli
20 s minuutin optimoinnin aikana (Tanjan kone 6.11.2026; ks.
tests/test_laskenta.py, joka kaatuu säieversiolla). Omassa prosessissaan ratkaisulla on oma
tulkkinsa ja GIL:nsä, eikä backend hidastu.

Prosessipooli luodaan laiskasti ensimmäisellä optimoinnilla (Windowsin
spawn-käynnistys tuo OR-Toolsin uuteen prosessiin muutamassa sekunnissa)
ja suljetaan sovelluksen sammuessa (ks. app/main.py). Ratkaistavat
funktiot ja niiden argumentit ovat moduulitason funktioita ja
dataclasseja, joten ne kulkevat picklellä prosessien välillä.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import logging
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Kaksi työprosessia: yksi optimointi + skenaariovertailu, tai kaksi eri
# päivää yhtä aikaa. Saman päivän päällekkäiset optimoinnit estetään
# routerissa (paivakohtainen_lukko).
_MAX_TYOPROSESSEJA = 2

_pooli: ProcessPoolExecutor | None = None


def _hae_pooli() -> ProcessPoolExecutor:
    global _pooli
    if _pooli is None:
        _pooli = ProcessPoolExecutor(max_workers=_MAX_TYOPROSESSEJA)
    return _pooli


async def aja_prosessissa(funktio: Callable[..., T], *args: Any) -> T:
    """Ajaa CPU-raskaan funktion työprosessissa ja odottaa tuloksen
    pysäyttämättä tapahtumasilmukkaa. Jos työprosessi on kaatunut
    (BrokenProcessPool), pooli luodaan uudelleen ja ajo yritetään kerran."""
    global _pooli
    silmukka = asyncio.get_running_loop()
    try:
        return await silmukka.run_in_executor(_hae_pooli(), funktio, *args)
    except BrokenProcessPool:
        logger.warning("Optimoinnin työprosessi kaatui, luodaan pooli uudelleen")
        sammuta_pooli()
        return await silmukka.run_in_executor(_hae_pooli(), funktio, *args)


def sammuta_pooli() -> None:
    global _pooli
    if _pooli is not None:
        _pooli.shutdown(wait=False, cancel_futures=True)
        _pooli = None


# --- Saman päivän päällekkäisten optimointien esto ---

_paivien_lukot: dict[int, asyncio.Lock] = {}


def paivan_lukko(paiva_id: int) -> asyncio.Lock:
    """Yksi optimointi kerrallaan per kuvauspäivä. Lukko on prosessin
    muistissa, mikä riittää yhden uvicorn-workerin ajossa (sama oletus kuin
    Nominatimin 1 kutsu/s -rajoitteessa, ks. geocoder_client.py)."""
    lukko = _paivien_lukot.get(paiva_id)
    if lukko is None:
        lukko = _paivien_lukot[paiva_id] = asyncio.Lock()
    return lukko

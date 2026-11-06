"""Moduulitason apufunktiot laskentaprosessitesteille. Työprosessiin
lähetettävän funktion pitää olla picklattavissa nimellä, joten nämä
eivät voi olla testifunktioiden sisäisiä sulkeumia."""

import os
import time

from app.services.optimoija import ratkaise


def oma_pid() -> int:
    return os.getpid()


def kuormittava_ratkaise(*args, **kwargs):
    """Pitää GIL:ää ~2 s kuten OR-Toolsin C++-ratkaisija: sum(range(n))
    pyörii C:ssä vapauttamatta GIL:ää eikä anna eval-silmukan vaihtaa
    säiettä kesken kutsun. Ratkaisee sitten oikeasti."""
    loppu = time.monotonic() + 2.0
    while time.monotonic() < loppu:
        sum(range(20_000_000))  # ~0.2-0.5 s yhtenä GIL:n pitona
    return ratkaise(*args, **kwargs)

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


def kuormittava_analyysi(*args, **kwargs):
    """Sama GIL:n pito kuin kuormittava_ratkaise, sijoittamattomien
    syyanalyysille (6.11.2026: analyysi ajettiin vielä pääprosessissa ja
    jumitti backendin minuuteiksi)."""
    from app.services.optimoija import analysoi_sijoittamattomat

    loppu = time.monotonic() + 2.0
    while time.monotonic() < loppu:
        sum(range(20_000_000))
    return analysoi_sijoittamattomat(*args, **kwargs)


def tallenna_analyysin_aikaraja(sijoittamatta_id, tehtavat, kuskit, ajoaika, parametrit):
    """Palauttaa saamansa aikarajan vastauksen kautta (työprosessista ei
    voi kirjoittaa testin muuttujiin)."""
    return [{"tehtava_id": -1, "nimi": f"aikaraja={parametrit.aikaraja_s}", "syy": "aikaikkuna", "selite": "testi"}]

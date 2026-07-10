"""Kuskin päivän lisäkustannus sopimustyypin mukaan (spec §2).

Tämä on tarkka jälkilaskenta valmiille ratkaisulle — eri asia kuin
OR-Toolsin hakua ohjaava kustannusmalli (ks. optimoija.py).
"""

from app.models import SopimusTyyppi

YLITYORAJA_1_H = 8.0
YLITYORAJA_2_H = 10.0
TUNTI_MINIMI_H = 4.0


def lisakustannus_eur(sopimus: SopimusTyyppi, minuutit: int, tuntihinta: float) -> float:
    """minuutit = työaika ensimmäisestä noudosta viimeiseen jättöön."""
    h = minuutit / 60

    if sopimus == SopimusTyyppi.KUUKAUSI:
        perus = 0.0
    elif sopimus == SopimusTyyppi.PAIVA:
        perus = YLITYORAJA_1_H * tuntihinta if minuutit > 0 else 0.0
    elif sopimus == SopimusTyyppi.TUNTI:
        h_veloitettava = max(h, TUNTI_MINIMI_H)
        perus = min(h_veloitettava, YLITYORAJA_1_H) * tuntihinta
    else:
        raise ValueError(f"Tuntematon sopimustyyppi: {sopimus}")

    yli8 = max(0.0, min(h, YLITYORAJA_2_H) - YLITYORAJA_1_H)
    yli10 = max(0.0, h - YLITYORAJA_2_H)
    return perus + yli8 * tuntihinta * 1.5 + yli10 * tuntihinta * 2.0

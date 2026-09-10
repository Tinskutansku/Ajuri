"""Roolin lukeminen pyynnöstä.

EI TURVAOMINAISUUS: rooli luetaan X-Rooli-headerista, jonka asiakas
asettaa itse - kuka tahansa voi väittää olevansa TUOTANTO. Tämä on
väliaikainen ratkaisu ennen autentikointia (docs/tuotekartta.md, V2 #5).
Se ohjaa vain mitä kenttiä API palauttaa, ei suojaa mitään - älä käytä
tätä minkään oikean pääsynhallinnan perustana.

Kun JWT-pohjainen autentikointi rakennetaan: korvataan TÄMÄN moduulin
`nykyinen_rooli`-funktion RUNKO lukemaan rooli tokenista. Kutsupaikat
(`Depends(nykyinen_rooli)`) reitittimissä eivät muutu.
"""

from fastapi import Header

from app.models import KayttajaRooli

OLETUSROOLI = KayttajaRooli.TUOTANTO


async def nykyinen_rooli(x_rooli: str | None = Header(default=None)) -> KayttajaRooli:
    if x_rooli is None:
        return OLETUSROOLI
    try:
        return KayttajaRooli(x_rooli.strip().lower())
    except ValueError:
        return OLETUSROOLI

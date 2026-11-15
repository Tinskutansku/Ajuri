"""Käyttäjä näkee vain oman tuotantonsa datan (ROADMAP K2).

Jokainen käyttäjä kuuluu yhteen tuotantoon (`kayttaja.tuotanto_id`,
sama arvo kuin tokenissa). Toisen tuotannon rivi näyttää käyttäjälle
samalta kuin olematon rivi: 404 samalla viestillä. Näin vastaus ei
paljasta, onko jollain toisella tuotannolla esim. henkilöä id:llä 7.

Resurssit kuuluvat tuotantoon kolmella tavalla:
- suoraan `tuotanto_id`-kentällä (henkilö, kuski, ajoneuvo, lokaatio,
  kuvauspäivä) tai tuotanto itse
- kuvauspäivän kautta `paiva_id`-kentällä (päivän henkilöt/kuskit/
  lokaatiot, tehtävät, ajolistaversiot)
- versio -> kuvauspäivä -ketjun kautta (keikat)
"""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AjolistaVersio, Kayttaja, Keikka, Kuvauspaiva, Tuotanto

TUOTANTOA_EI_LOYTYNYT = "Tuotantoa ei löytynyt"
PAIVAA_EI_LOYTYNYT = "Kuvauspäivää ei löytynyt"
VERSIOTA_EI_LOYTYNYT = "Versiota ei löytynyt"


def _404(viesti: str) -> HTTPException:
    return HTTPException(status_code=404, detail=viesti)


def tarkista_tuotanto(tuotanto_id: int, kayttaja: Kayttaja) -> None:
    """Pyynnössä annettu tuotanto_id (esim. luonnin runko tai listauksen
    suodatin) on oltava käyttäjän oma."""
    if tuotanto_id != kayttaja.tuotanto_id:
        raise _404(TUOTANTOA_EI_LOYTYNYT)


async def hae_tuotanto(db: AsyncSession, tuotanto_id: int, kayttaja: Kayttaja) -> Tuotanto:
    tarkista_tuotanto(tuotanto_id, kayttaja)
    tuotanto = await db.get(Tuotanto, tuotanto_id)
    if tuotanto is None:
        raise _404(TUOTANTOA_EI_LOYTYNYT)
    return tuotanto


async def hae_tuotannon_rivi(db: AsyncSession, malli: type, rivi_id: int, kayttaja: Kayttaja, viesti: str) -> Any:
    """Rivi mallista, jolla on oma `tuotanto_id` (Henkilo, Kuski, ...)."""
    rivi = await db.get(malli, rivi_id)
    if rivi is None or rivi.tuotanto_id != kayttaja.tuotanto_id:
        raise _404(viesti)
    return rivi


async def hae_paiva(
    db: AsyncSession, paiva_id: int, kayttaja: Kayttaja, viesti: str = PAIVAA_EI_LOYTYNYT
) -> Kuvauspaiva:
    return await hae_tuotannon_rivi(db, Kuvauspaiva, paiva_id, kayttaja, viesti)


async def hae_paivan_rivi(db: AsyncSession, malli: type, rivi_id: int, kayttaja: Kayttaja, viesti: str) -> Any:
    """Rivi mallista, joka kuuluu tuotantoon kuvauspäivän (`paiva_id`) kautta."""
    rivi = await db.get(malli, rivi_id)
    if rivi is None:
        raise _404(viesti)
    await hae_paiva(db, rivi.paiva_id, kayttaja, viesti)
    return rivi


async def hae_versio(
    db: AsyncSession, versio_id: int, kayttaja: Kayttaja, viesti: str = VERSIOTA_EI_LOYTYNYT
) -> AjolistaVersio:
    return await hae_paivan_rivi(db, AjolistaVersio, versio_id, kayttaja, viesti)


async def hae_keikka(db: AsyncSession, keikka_id: int, kayttaja: Kayttaja, viesti: str) -> Keikka:
    keikka = await db.get(Keikka, keikka_id)
    if keikka is None:
        raise _404(viesti)
    await hae_versio(db, keikka.versio_id, kayttaja, viesti)
    return keikka


async def tarkista_viite(
    db: AsyncSession, malli: type, rivi_id: int | None, kayttaja: Kayttaja, viesti: str
) -> None:
    """Rungossa viitattu rivi (esim. päivän henkilön henkilo_id) ei saa
    kuulua toiseen tuotantoon. Puuttuva viite (None) tai olematon rivi
    käsitellään kuten ennenkin, eli tämä ei muuta niiden käytöstä."""
    if rivi_id is None:
        return
    rivi = await db.get(malli, rivi_id)
    if rivi is None:
        return
    tuotanto_id = rivi.tuotanto_id if hasattr(rivi, "tuotanto_id") else None
    if tuotanto_id is None and hasattr(rivi, "paiva_id"):
        paiva = await db.get(Kuvauspaiva, rivi.paiva_id)
        tuotanto_id = paiva.tuotanto_id if paiva else None
    if tuotanto_id != kayttaja.tuotanto_id:
        raise _404(viesti)


def rajaa_tuotantoon(stmt: Select, malli: type, kayttaja: Kayttaja) -> Select:
    """Listaus mallista, jolla on oma tuotanto_id."""
    return stmt.where(malli.tuotanto_id == kayttaja.tuotanto_id)


def rajaa_paivan_kautta(stmt: Select, malli: type, kayttaja: Kayttaja) -> Select:
    """Listaus mallista, joka kuuluu tuotantoon kuvauspäivän kautta."""
    return stmt.join(Kuvauspaiva, Kuvauspaiva.id == malli.paiva_id).where(
        Kuvauspaiva.tuotanto_id == kayttaja.tuotanto_id
    )

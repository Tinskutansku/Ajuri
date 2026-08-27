"""Seed-skripti: luo/päivittää yhden realistisen kuvauspäivän demo-/
kehityskäyttöön.

Idempotentti — jokainen rivi haetaan luonnollisella avaimella (esim.
tuotanto+nimi, päivä+henkilö) ja jos se löytyy, sen muut kentät päivitetään
vastaamaan tätä skriptiä. Uudelleenajo siis konvergoi aina samaan
lopputilaan eikä koskaan luo duplikaatteja.

Käyttö:
    python -m app.seed
"""

from __future__ import annotations

import asyncio
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import (
    Ajoneuvo,
    Henkilo,
    HenkiloTyyppi,
    Kuski,
    Kuvauspaiva,
    Lokaatio,
    PaivaHenkilo,
    PaivaKuski,
    PaivaLokaatio,
    SopimusTyyppi,
    Tehtava,
    TehtavaTyyppi,
    Tuotanto,
)

TUOTANTO_NIMI = "Demo — Pääkaupunkiseutu"
PAIVA_PVM = date(2026, 9, 15)
WRAP = time(18, 0)

# ---------------------------------------------------------------------------
# Koordinaatit — oikeita pääkaupunkiseudun pisteitä, jotta OSRM antaa
# uskottavia ajoaikoja (osoite, lat, lon).
# ---------------------------------------------------------------------------

HOTELLI_KAMP = ("Hotel Kämp, Pohjoisesplanadi 29, Helsinki", 60.1683, 24.9427)
HOTELLI_SIMONKENTTA = ("Scandic Simonkenttä, Simonkatu 9, Helsinki", 60.1699, 24.9313)
KOTI_NAYTTELIJA3 = ("Kotiosoite, Tapiola, Espoo", 60.1756, 24.8058)
KOTI_NAYTTELIJA4 = ("Kotiosoite, Leppävaara, Espoo", 60.2188, 24.8131)
KUVAUSPAIKKA = ("Kuvauspaikka, Otaniemi, Espoo", 60.1841, 24.8306)
TOIMISTO = ("Tuotantotoimisto, Ruoholahti, Helsinki", 60.1596, 24.9153)
CATERING = ("Catering, Keilaniemi, Espoo", 60.1755, 24.8272)
LENTOASEMA = ("Helsinki-Vantaan lentoasema", 60.3172, 24.9633)

KOTI_KUSKI1 = ("Kotiosoite, Tapiola, Espoo", 60.1799, 24.8046)
KOTI_KUSKI2 = ("Kotiosoite, Kallio, Helsinki", 60.1836, 24.9500)
KOTI_KUSKI3 = ("Kotiosoite, Tikkurila, Vantaa", 60.2934, 25.0378)
KOTI_KUSKI4 = ("Kotiosoite, Leppävaara, Espoo", 60.2170, 24.8110)


async def upsert(db: AsyncSession, model, defaults: dict | None = None, **kwargs):
    """Hakee rivin annetulla luonnollisella avaimella (kwargs). Jos rivi
    löytyy, sen defaults-kentät päivitetään vastaamaan tätä ajoa; jos ei
    löydy, rivi luodaan kwargs+defaults-kentillä. Näin skripti on aidosti
    idempotentti myös silloin kun sisältöä muokataan ajojen välissä."""
    result = await db.execute(select(model).filter_by(**kwargs))
    instance = result.scalar_one_or_none()
    if instance is None:
        instance = model(**kwargs, **(defaults or {}))
        db.add(instance)
    else:
        for kentta, arvo in (defaults or {}).items():
            setattr(instance, kentta, arvo)
    await db.flush()
    return instance


async def main() -> None:
    async with AsyncSessionLocal() as db:
        tuotanto = await upsert(
            db, Tuotanto, nimi=TUOTANTO_NIMI, defaults={"tuntihinta_eur": 22.0}
        )

        paiva = await upsert(
            db,
            Kuvauspaiva,
            tuotanto_id=tuotanto.id,
            pvm=PAIVA_PVM,
            defaults={
                "paiva_nro": "1/1",
                "call_time": time(8, 0),
                "lounas": time(12, 30),
                "wrap_arvio": WRAP,
                "huomiot": "Demo-kuvauspäivä pääkaupunkiseudulla",
            },
        )

        # --- Henkilöt: 4 näyttelijää + ohjaaja + apulaisohjaaja + 2 tr-läistä ---
        nayt1 = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Näyttelijä 1",
            defaults={
                "tyyppi": HenkiloTyyppi.CAST, "roolinimi": "Pääosa",
                "osoite": HOTELLI_KAMP[0], "lat": HOTELLI_KAMP[1], "lon": HOTELLI_KAMP[2],
            },
        )
        nayt2 = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Näyttelijä 2",
            defaults={
                "tyyppi": HenkiloTyyppi.CAST, "roolinimi": "Sivuosa",
                "osoite": HOTELLI_KAMP[0], "lat": HOTELLI_KAMP[1], "lon": HOTELLI_KAMP[2],
            },
        )
        nayt3 = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Näyttelijä 3",
            defaults={
                "tyyppi": HenkiloTyyppi.CAST, "roolinimi": "Sivuosa",
                "osoite": KOTI_NAYTTELIJA3[0], "lat": KOTI_NAYTTELIJA3[1], "lon": KOTI_NAYTTELIJA3[2],
            },
        )
        nayt4 = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Näyttelijä 4",
            defaults={
                "tyyppi": HenkiloTyyppi.CAST, "roolinimi": "Iltapäiväkohtaus",
                "osoite": KOTI_NAYTTELIJA4[0], "lat": KOTI_NAYTTELIJA4[1], "lon": KOTI_NAYTTELIJA4[2],
            },
        )
        ohjaaja = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Ohjaaja",
            defaults={
                "tyyppi": HenkiloTyyppi.CREW, "titteli": "Ohjaaja",
                "osoite": HOTELLI_SIMONKENTTA[0], "lat": HOTELLI_SIMONKENTTA[1],
                "lon": HOTELLI_SIMONKENTTA[2],
            },
        )
        apulaisohjaaja = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Apulaisohjaaja",
            defaults={
                "tyyppi": HenkiloTyyppi.CREW, "titteli": "Apulaisohjaaja",
                "osoite": HOTELLI_SIMONKENTTA[0], "lat": HOTELLI_SIMONKENTTA[1],
                "lon": HOTELLI_SIMONKENTTA[2], "oletus_oma_auto": True,
            },
        )
        tr1 = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Työryhmäläinen 1",
            defaults={
                "tyyppi": HenkiloTyyppi.CREW, "titteli": "Puvustaja",
                "osoite": HOTELLI_SIMONKENTTA[0], "lat": HOTELLI_SIMONKENTTA[1],
                "lon": HOTELLI_SIMONKENTTA[2],
            },
        )
        tr2 = await upsert(
            db, Henkilo, tuotanto_id=tuotanto.id, nimi="Työryhmäläinen 2",
            defaults={
                "tyyppi": HenkiloTyyppi.CREW, "titteli": "Maskeeraaja",
                "osoite": HOTELLI_SIMONKENTTA[0], "lat": HOTELLI_SIMONKENTTA[1],
                "lon": HOTELLI_SIMONKENTTA[2],
            },
        )

        # --- Kuskit: 2 kk-sopimusta, 1 päiväpalkka, 1 tuntipalkka ---
        # Huom: speksissä oli "2 farmaria + 1 minibussi" neljälle kuskille,
        # mutta jokainen tarjolla oleva kuski tarvitsee oman ajoneuvon
        # (optimointi-endpoint vaatii sitä) — lisätty siksi 3. farmari.
        kuski1 = await upsert(
            db, Kuski, tuotanto_id=tuotanto.id, nimi="Kuski 1",
            defaults={
                "sopimus": SopimusTyyppi.KUUKAUSI,
                "koti_osoite": KOTI_KUSKI1[0], "koti_lat": KOTI_KUSKI1[1], "koti_lon": KOTI_KUSKI1[2],
            },
        )
        kuski2 = await upsert(
            db, Kuski, tuotanto_id=tuotanto.id, nimi="Kuski 2",
            defaults={
                "sopimus": SopimusTyyppi.KUUKAUSI,
                "koti_osoite": KOTI_KUSKI2[0], "koti_lat": KOTI_KUSKI2[1], "koti_lon": KOTI_KUSKI2[2],
            },
        )
        kuski3 = await upsert(
            db, Kuski, tuotanto_id=tuotanto.id, nimi="Kuski 3",
            defaults={
                "sopimus": SopimusTyyppi.PAIVA,
                "koti_osoite": KOTI_KUSKI3[0], "koti_lat": KOTI_KUSKI3[1], "koti_lon": KOTI_KUSKI3[2],
            },
        )
        kuski4 = await upsert(
            db, Kuski, tuotanto_id=tuotanto.id, nimi="Kuski 4 (extra)",
            defaults={
                "sopimus": SopimusTyyppi.TUNTI, "tuntihinta_eur": 24.0,
                "koti_osoite": KOTI_KUSKI4[0], "koti_lat": KOTI_KUSKI4[1], "koti_lon": KOTI_KUSKI4[2],
            },
        )

        # --- Ajoneuvot: 3 farmaria (mukavuus 3) + 1 minibussi (mukavuus 8) ---
        farmari1 = await upsert(
            db, Ajoneuvo, tuotanto_id=tuotanto.id, nimi="Farmari 1",
            defaults={"rekisteri": "ABC-111", "mukavuuspaikat": 3, "max_paikat": 4},
        )
        farmari2 = await upsert(
            db, Ajoneuvo, tuotanto_id=tuotanto.id, nimi="Farmari 2",
            defaults={"rekisteri": "ABC-222", "mukavuuspaikat": 3, "max_paikat": 4},
        )
        farmari3 = await upsert(
            db, Ajoneuvo, tuotanto_id=tuotanto.id, nimi="Farmari 3",
            defaults={"rekisteri": "ABC-333", "mukavuuspaikat": 3, "max_paikat": 4},
        )
        minibussi = await upsert(
            db, Ajoneuvo, tuotanto_id=tuotanto.id, nimi="Minibussi 1",
            defaults={"rekisteri": "DEF-888", "mukavuuspaikat": 8, "max_paikat": 8},
        )

        # --- Lokaatio + PaivaLokaatio ---
        kuvauspaikka_lokaatio = await upsert(
            db, Lokaatio, tuotanto_id=tuotanto.id, nimi="Kuvauspaikka",
            defaults={
                "osoite": KUVAUSPAIKKA[0], "lat": KUVAUSPAIKKA[1], "lon": KUVAUSPAIKKA[2],
            },
        )
        await upsert(
            db, PaivaLokaatio, paiva_id=paiva.id, lokaatio_id=kuvauspaikka_lokaatio.id,
            defaults={"jarjestys": 1},
        )

        # --- PaivaHenkilo (kaikki 8, apulaisohjaajalla oma auto -> ei kuljetusta) ---
        await upsert(
            db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=nayt1.id,
            defaults={"oma_call": time(6, 30)},
        )
        await upsert(db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=nayt2.id)
        await upsert(
            db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=nayt3.id,
            defaults={"oma_call": time(8, 30)},
        )
        await upsert(
            db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=nayt4.id,
            defaults={"oma_call": time(14, 45)},
        )
        await upsert(db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=ohjaaja.id)
        await upsert(
            db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=apulaisohjaaja.id,
            defaults={"oma_auto": True, "siirtyy": False},
        )
        await upsert(db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=tr1.id)
        await upsert(db, PaivaHenkilo, paiva_id=paiva.id, henkilo_id=tr2.id)

        # --- PaivaKuski (kaikki 4 tarjolla, kukin omalla ajoneuvollaan) ---
        await upsert(
            db, PaivaKuski, paiva_id=paiva.id, kuski_id=kuski1.id,
            defaults={"ajoneuvo_id": farmari1.id, "tarjolla": True},
        )
        await upsert(
            db, PaivaKuski, paiva_id=paiva.id, kuski_id=kuski2.id,
            defaults={"ajoneuvo_id": farmari2.id, "tarjolla": True},
        )
        await upsert(
            db, PaivaKuski, paiva_id=paiva.id, kuski_id=kuski3.id,
            defaults={"ajoneuvo_id": minibussi.id, "tarjolla": True},
        )
        await upsert(
            db, PaivaKuski, paiva_id=paiva.id, kuski_id=kuski4.id,
            defaults={"ajoneuvo_id": farmari3.id, "tarjolla": True},
        )

        # --- Tehtävät: henkilönoudot, paluukyydit wrapin jälkeen + erikoiskeikat ---
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Nouto: Näyttelijä 1 (maski)",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkilo_id": nayt1.id, "henkiloita": 1,
                "mista_osoite": HOTELLI_KAMP[0], "mista_lat": HOTELLI_KAMP[1], "mista_lon": HOTELLI_KAMP[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": time(6, 30),
                "lukittu_kuski_id": kuski1.id,
                "huomiot": "maski 1,5 h ennen calliä - päivän ensimmäinen call. "
                           "Kuski 1 hakee aina Näyttelijä 1:n (kiinteä kuski koko päiväksi).",
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Nouto: Näyttelijä 2",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkilo_id": nayt2.id, "henkiloita": 1,
                "mista_osoite": HOTELLI_KAMP[0], "mista_lat": HOTELLI_KAMP[1], "mista_lon": HOTELLI_KAMP[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": time(8, 0),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Nouto: Näyttelijä 3",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkilo_id": nayt3.id, "henkiloita": 1,
                "mista_osoite": KOTI_NAYTTELIJA3[0], "mista_lat": KOTI_NAYTTELIJA3[1],
                "mista_lon": KOTI_NAYTTELIJA3[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": time(8, 30),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Nouto: Näyttelijä 4 (iltapäiväkohtaus)",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkilo_id": nayt4.id, "henkiloita": 1,
                "mista_osoite": KOTI_NAYTTELIJA4[0], "mista_lat": KOTI_NAYTTELIJA4[1],
                "mista_lon": KOTI_NAYTTELIJA4[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": time(14, 45),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Nouto: Ohjaaja",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkilo_id": ohjaaja.id, "henkiloita": 1,
                "mista_osoite": HOTELLI_SIMONKENTTA[0], "mista_lat": HOTELLI_SIMONKENTTA[1],
                "mista_lon": HOTELLI_SIMONKENTTA[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": time(8, 0),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Työryhmä-shuttle (2 hlö)",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkiloita": 2,
                "mista_osoite": HOTELLI_SIMONKENTTA[0], "mista_lat": HOTELLI_SIMONKENTTA[1],
                "mista_lon": HOTELLI_SIMONKENTTA[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": time(8, 0),
                "huomiot": "Työryhmäläinen 1 + Työryhmäläinen 2",
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Lounashaku",
            defaults={
                "tyyppi": TehtavaTyyppi.TAVARA, "henkiloita": 0,
                "mista_osoite": CATERING[0], "mista_lat": CATERING[1], "mista_lon": CATERING[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "nouto_aikaisintaan": time(11, 15), "perilla_viimeistaan": time(12, 5),
                "huomiot": "ruoka settiin ennen lounasta",
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Rekvisiitan haku toimistolta",
            defaults={
                "tyyppi": TehtavaTyyppi.TAVARA, "henkiloita": 0,
                "mista_osoite": TOIMISTO[0], "mista_lat": TOIMISTO[1], "mista_lon": TOIMISTO[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "nouto_aikaisintaan": time(10, 0), "perilla_viimeistaan": time(11, 0),
                "huomiot": "aamupäivän rekvisiittatäydennys",
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Kortit toimistolle",
            defaults={
                "tyyppi": TehtavaTyyppi.TAVARA, "henkiloita": 0,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": TOIMISTO[0], "mihin_lat": TOIMISTO[1], "mihin_lon": TOIMISTO[2],
                "nouto_aikaisintaan": time(15, 0),
                "huomiot": "päivän kuvausmateriaali toimistolle",
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Lentokenttänouto (vieraileva näyttelijä)",
            defaults={
                "tyyppi": TehtavaTyyppi.HENKILO, "henkiloita": 1,
                "mista_osoite": LENTOASEMA[0], "mista_lat": LENTOASEMA[1], "mista_lon": LENTOASEMA[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
                "nouto_aikaisintaan": time(15, 40), "nouto_viimeistaan": time(16, 10),
                "perilla_viimeistaan": time(16, 45),
                "huomiot": "lento laskeutuu 15:25",
            },
        )

        # --- Paluukyydit wrapin jälkeen (klo 18:00, max 25 min odotusta) ---
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Paluu: Näyttelijä 1",
            defaults={
                "tyyppi": TehtavaTyyppi.PALUU, "henkilo_id": nayt1.id, "henkiloita": 1,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": HOTELLI_KAMP[0], "mihin_lat": HOTELLI_KAMP[1], "mihin_lon": HOTELLI_KAMP[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 25),
                "lukittu_kuski_id": kuski1.id,
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Paluu: Näyttelijä 2",
            defaults={
                "tyyppi": TehtavaTyyppi.PALUU, "henkilo_id": nayt2.id, "henkiloita": 1,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": HOTELLI_KAMP[0], "mihin_lat": HOTELLI_KAMP[1], "mihin_lon": HOTELLI_KAMP[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 25),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Paluu: Näyttelijä 3",
            defaults={
                "tyyppi": TehtavaTyyppi.PALUU, "henkilo_id": nayt3.id, "henkiloita": 1,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": KOTI_NAYTTELIJA3[0], "mihin_lat": KOTI_NAYTTELIJA3[1],
                "mihin_lon": KOTI_NAYTTELIJA3[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 25),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Paluu: Näyttelijä 4",
            defaults={
                "tyyppi": TehtavaTyyppi.PALUU, "henkilo_id": nayt4.id, "henkiloita": 1,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": KOTI_NAYTTELIJA4[0], "mihin_lat": KOTI_NAYTTELIJA4[1],
                "mihin_lon": KOTI_NAYTTELIJA4[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 25),
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Paluu: Ohjaaja + työryhmä (3 hlö)",
            defaults={
                "tyyppi": TehtavaTyyppi.PALUU, "henkiloita": 3,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": HOTELLI_SIMONKENTTA[0], "mihin_lat": HOTELLI_SIMONKENTTA[1],
                "mihin_lon": HOTELLI_SIMONKENTTA[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 25),
                "huomiot": "Ohjaaja + Työryhmäläinen 1 + Työryhmäläinen 2",
            },
        )
        await upsert(
            db, Tehtava, paiva_id=paiva.id, nimi="Paluu: vieraileva näyttelijä lentokentälle",
            defaults={
                "tyyppi": TehtavaTyyppi.PALUU, "henkiloita": 1, "yksin": True,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": LENTOASEMA[0], "mihin_lat": LENTOASEMA[1], "mihin_lon": LENTOASEMA[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 20),
                "huomiot": "lento klo 20:10 - ei odotuttamista, ei kimppakyytiä",
            },
        )

        await db.commit()

        tehtava_maara = (
            await db.execute(select(Tehtava).where(Tehtava.paiva_id == paiva.id))
        ).scalars().all()

        print(f"Tuotanto: {tuotanto.nimi} (id={tuotanto.id})")
        print(f"Kuvauspäivä: {paiva.pvm} (id={paiva.id}), call {paiva.call_time}, wrap {paiva.wrap_arvio}")
        print(f"Tehtäviä yhteensä: {len(tehtava_maara)}")
        print("Valmis. Kokeile optimointia:")
        print(f"  POST /paivat/{paiva.id}/optimoi")


if __name__ == "__main__":
    asyncio.run(main())

"""Seed-skripti: luo/päivittää yhden realistisen kuvauspäivän demo-/
kehityskäyttöön.

Idempotentti — jokainen rivi haetaan luonnollisella avaimella (esim.
tuotanto+nimi, päivä+henkilö) ja jos se löytyy, sen muut kentät päivitetään
vastaamaan tätä skriptiä. Uudelleenajo siis konvergoi aina samaan
lopputilaan eikä koskaan luo duplikaatteja.

Henkilöiden noudot ja paluut ovat samat, jotka "Generoi tehtävät"
(POST /paivat/{id}/generoi-tehtavat) tuottaisi, ja ne on merkitty
generoitu=true. Generointi siis korvaa ne eikä tuplaa niitä. Erikoiskeikat
(lounashaku, rekvisiitta, kortit, lentokenttä) ovat käsin lisättyjä.

Käyttö:
    python -m app.seed
"""

from __future__ import annotations

import asyncio
from datetime import date, time

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hashaa_salasana, tarkista_salasana
from app.database import AsyncSessionLocal
from app.models import (
    Ajoneuvo,
    Henkilo,
    HenkiloTyyppi,
    Kayttaja,
    KayttajaRooli,
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
KOTI_KUSKI5 = ("Vuokraamo, Pasila, Helsinki", 60.1984, 24.9339)

# Aiempien seed-versioiden käsin lisätyt henkilökyydit, joiden tilalle tulevat
# nyt generoinnin mukaiset henkilökohtaiset noudot ja paluut. Uudelleenajo
# poistaa nämä (soft delete), jotta vanha kanta korjautuu ilman tuplia.
# Demokäyttäjät tunnetuilla salasanoilla (README, "Demokäyttäjät").
# VAIN demo-/kehityskäyttöön - älä aja seediä oikean tuotannon kantaan.
# (email, nimi, rooli, salasana); kuski-käyttäjä linkitetään Kuski 1:een.
DEMOKAYTTAJAT = [
    ("tuotanto@ajuri.example", "Demo Tuotanto", KayttajaRooli.TUOTANTO, "demo-tuotanto"),
    ("koordi@ajuri.example", "Demo Koordinaattori", KayttajaRooli.KOORDI, "demo-koordi"),
    ("kuski@ajuri.example", "Demo Kuski (Kuski 1)", KayttajaRooli.KUSKI, "demo-kuski"),
]

VANHAT_TEHTAVANIMET = [
    "Nouto: Näyttelijä 1 (maski)",
    "Nouto: Näyttelijä 4 (iltapäiväkohtaus)",
    "Työryhmä-shuttle (2 hlö)",
    "Paluu: Ohjaaja + työryhmä (3 hlö)",
]


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


async def upsert_tehtava(db: AsyncSession, paiva_id: int, nimi: str, defaults: dict) -> Tehtava:
    """Tehtävän upsert avaimella (päivä, nimi).

    Tehtävillä nimi ei ole yksikäsitteinen: generointi soft-deletoi vanhat
    generoidut rivit ja luo samannimiset uudet. Siksi ensisijaisesti
    päivitetään aktiivinen rivi (vanhin), ja muut samannimiset aktiiviset
    rivit poistetaan (soft delete), jolloin vanhaan kantaan jääneet tuplat
    siivoutuvat. Jos aktiivista ei ole, päivitetään uusin passiivinen rivi
    sen aktiivisuutta muuttamatta (käyttäjän poistama tehtävä pysyy
    poistettuna), ja muuten luodaan uusi."""
    rivit = (
        await db.execute(
            select(Tehtava)
            .where(Tehtava.paiva_id == paiva_id, Tehtava.nimi == nimi)
            .order_by(Tehtava.id)
        )
    ).scalars().all()
    aktiiviset = [r for r in rivit if r.aktiivinen]
    if aktiiviset:
        instance = aktiiviset[0]
        for tupla in aktiiviset[1:]:
            tupla.aktiivinen = False
    elif rivit:
        instance = rivit[-1]
    else:
        instance = Tehtava(paiva_id=paiva_id, nimi=nimi)
        db.add(instance)
    for kentta, arvo in defaults.items():
        setattr(instance, kentta, arvo)
    await db.flush()
    return instance


async def seed(db: AsyncSession) -> tuple[Tuotanto, Kuvauspaiva]:
    """Luo tai päivittää demo-kuvauspäivän annettuun sessioon ja committaa.
    Erillään main():sta, jotta testit voivat ajaa seedin muistikantaan."""
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

    # --- Kuskit: 2 kk-sopimusta, 1 päiväpalkka, 1 tuntipalkka + 1 kk-sopimus
    # joka on tarjolla vasta illalla (vuoro_aikaisintaan) ---
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
    # Kuukausisopimuksinen, mutta tarjolla vasta illalla (vuoro_aikaisintaan) -
    # esim. hoitaa päivällä muita tuotannon vuokra-autohommia.
    kuski5 = await upsert(
        db, Kuski, tuotanto_id=tuotanto.id, nimi="Kuvaaja / vuokra-auto",
        defaults={
            "sopimus": SopimusTyyppi.KUUKAUSI,
            "koti_osoite": KOTI_KUSKI5[0], "koti_lat": KOTI_KUSKI5[1], "koti_lon": KOTI_KUSKI5[2],
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
    vuokra_auto = await upsert(
        db, Ajoneuvo, tuotanto_id=tuotanto.id, nimi="Vuokra-auto",
        defaults={"rekisteri": "GHI-999", "mukavuuspaikat": 3, "max_paikat": 4},
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

    # --- PaivaKuski (kaikki 5 tarjolla, kukin omalla ajoneuvollaan;
    # Kuvaaja/vuokra-auto vasta klo 18 alkaen) ---
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
    await upsert(
        db, PaivaKuski, paiva_id=paiva.id, kuski_id=kuski5.id,
        defaults={
            "ajoneuvo_id": vuokra_auto.id, "tarjolla": True,
            "vuoro_aikaisintaan": time(18, 0),
        },
    )

    # --- Tehtävät 1/2: henkilönoudot ja paluut ------------------------
    # Nämä ovat täsmälleen ne rivit, jotka POST /paivat/{id}/generoi-tehtavat
    # tuottaisi päivän henkilöistä (sama nimi, reitti ja aikaikkuna), joten
    # ne merkitään generoitu=true. Generointi korvaa ne uusilla eikä tuplaa
    # niitä. Apulaisohjaajalla on oma auto, joten hänelle ei tule kyytejä.
    # Huom: generointi ei tunne lukittua kuskia eikä huomioita, joten
    # Näyttelijä 1:n kiinteä kuski katoaa, jos tehtävät generoidaan uudelleen.
    noudettavat = [
        # (henkilö, kotiosoite, perillä viimeistään = oma call tai päivän call)
        (nayt1, HOTELLI_KAMP, time(6, 30)),
        (nayt2, HOTELLI_KAMP, paiva.call_time),
        (nayt3, KOTI_NAYTTELIJA3, time(8, 30)),
        (nayt4, KOTI_NAYTTELIJA4, time(14, 45)),
        (ohjaaja, HOTELLI_SIMONKENTTA, paiva.call_time),
        (tr1, HOTELLI_SIMONKENTTA, paiva.call_time),
        (tr2, HOTELLI_SIMONKENTTA, paiva.call_time),
    ]
    lisatiedot = {
        ("Nouto", nayt1.id): {
            "lukittu_kuski_id": kuski1.id,
            "huomiot": "maski 1,5 h ennen calliä - päivän ensimmäinen call. "
                       "Kuski 1 hakee aina Näyttelijä 1:n (kiinteä kuski koko päiväksi).",
        },
        ("Paluu", nayt1.id): {"lukittu_kuski_id": kuski1.id},
        ("Nouto", nayt4.id): {"huomiot": "iltapäiväkohtaus"},
    }
    for henkilo, koti, perilla in noudettavat:
        await upsert_tehtava(
            db, paiva.id, f"Nouto: {henkilo.nimi}",
            {
                "tyyppi": TehtavaTyyppi.HENKILO, "henkilo_id": henkilo.id, "henkiloita": 1,
                "mista_osoite": koti[0], "mista_lat": koti[1], "mista_lon": koti[2],
                "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1],
                "mihin_lon": KUVAUSPAIKKA[2],
                "perilla_viimeistaan": perilla,
                "generoitu": True,
                "lukittu_kuski_id": None, "huomiot": None,
                **lisatiedot.get(("Nouto", henkilo.id), {}),
            },
        )
        await upsert_tehtava(
            db, paiva.id, f"Paluu: {henkilo.nimi}",
            {
                "tyyppi": TehtavaTyyppi.PALUU, "henkilo_id": henkilo.id, "henkiloita": 1,
                "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1],
                "mista_lon": KUVAUSPAIKKA[2],
                "mihin_osoite": koti[0], "mihin_lat": koti[1], "mihin_lon": koti[2],
                "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 25),
                "generoitu": True,
                "lukittu_kuski_id": None, "huomiot": None,
                **lisatiedot.get(("Paluu", henkilo.id), {}),
            },
        )

    # Aiempien seed-versioiden käsin lisätyt henkilökyydit, jotka nyt
    # korvautuvat yllä olevilla. Poistetaan (soft delete), jotta
    # uudelleenajo korjaa vanhan kannan ilman tuplia.
    await db.execute(
        update(Tehtava)
        .where(
            Tehtava.paiva_id == paiva.id,
            Tehtava.nimi.in_(VANHAT_TEHTAVANIMET),
            Tehtava.aktiivinen.is_(True),
        )
        .values(aktiivinen=False)
    )

    # --- Tehtävät 2/2: erikoiskeikat, jotka jäävät käsin lisätyiksi ---
    await upsert_tehtava(
        db, paiva.id, "Lounashaku",
        {
            "tyyppi": TehtavaTyyppi.TAVARA, "henkiloita": 0,
            "mista_osoite": CATERING[0], "mista_lat": CATERING[1], "mista_lon": CATERING[2],
            "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
            "nouto_aikaisintaan": time(11, 15), "perilla_viimeistaan": time(12, 5),
            "huomiot": "ruoka settiin ennen lounasta",
        },
    )
    await upsert_tehtava(
        db, paiva.id, "Rekvisiitan haku toimistolta",
        {
            "tyyppi": TehtavaTyyppi.TAVARA, "henkiloita": 0,
            "mista_osoite": TOIMISTO[0], "mista_lat": TOIMISTO[1], "mista_lon": TOIMISTO[2],
            "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
            "nouto_aikaisintaan": time(10, 0), "perilla_viimeistaan": time(11, 0),
            "huomiot": "aamupäivän rekvisiittatäydennys",
        },
    )
    await upsert_tehtava(
        db, paiva.id, "Kortit toimistolle",
        {
            "tyyppi": TehtavaTyyppi.TAVARA, "henkiloita": 0,
            "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
            "mihin_osoite": TOIMISTO[0], "mihin_lat": TOIMISTO[1], "mihin_lon": TOIMISTO[2],
            "nouto_aikaisintaan": time(15, 0),
            "huomiot": "päivän kuvausmateriaali toimistolle",
        },
    )
    await upsert_tehtava(
        db, paiva.id, "Lentokenttänouto (vieraileva näyttelijä)",
        {
            "tyyppi": TehtavaTyyppi.HENKILO, "henkiloita": 1,
            "mista_osoite": LENTOASEMA[0], "mista_lat": LENTOASEMA[1], "mista_lon": LENTOASEMA[2],
            "mihin_osoite": KUVAUSPAIKKA[0], "mihin_lat": KUVAUSPAIKKA[1], "mihin_lon": KUVAUSPAIKKA[2],
            "nouto_aikaisintaan": time(15, 40), "nouto_viimeistaan": time(16, 10),
            "perilla_viimeistaan": time(16, 45),
            "huomiot": "lento laskeutuu 15:25",
        },
    )
    await upsert_tehtava(
        db, paiva.id, "Paluu: vieraileva näyttelijä lentokentälle",
        {
            "tyyppi": TehtavaTyyppi.PALUU, "henkiloita": 1, "yksin": True,
            "mista_osoite": KUVAUSPAIKKA[0], "mista_lat": KUVAUSPAIKKA[1], "mista_lon": KUVAUSPAIKKA[2],
            "mihin_osoite": LENTOASEMA[0], "mihin_lat": LENTOASEMA[1], "mihin_lon": LENTOASEMA[2],
            "nouto_aikaisintaan": WRAP, "nouto_viimeistaan": time(18, 20),
            "huomiot": "lento klo 20:10 - ei odotuttamista, ei kimppakyytiä",
        },
    )

    await seed_kayttajat(db, tuotanto.id, kuski1.id)

    await db.commit()
    return tuotanto, paiva


async def seed_kayttajat(db: AsyncSession, tuotanto_id: int, kuski_id: int) -> None:
    """Demokäyttäjät. Hash vaihdetaan vain, jos nykyinen ei täsmää
    demosalasanaan, jotta uudelleenajo ei turhaan muuta riviä."""
    for email, nimi, rooli, salasana in DEMOKAYTTAJAT:
        kayttaja = await upsert(
            db, Kayttaja, email=email,
            defaults={
                "tuotanto_id": tuotanto_id, "nimi": nimi, "rooli": rooli,
                "kuski_id": kuski_id if rooli == KayttajaRooli.KUSKI else None,
                "aktiivinen": True,
            },
        )
        if not tarkista_salasana(kayttaja.salasana_hash, salasana):
            kayttaja.salasana_hash = hashaa_salasana(salasana)
    await db.flush()


async def main() -> None:
    async with AsyncSessionLocal() as db:
        tuotanto, paiva = await seed(db)

        tehtavat = (
            await db.execute(
                select(Tehtava).where(Tehtava.paiva_id == paiva.id, Tehtava.aktiivinen.is_(True))
            )
        ).scalars().all()

        print(f"Tuotanto: {tuotanto.nimi} (id={tuotanto.id})")
        print(f"Kuvauspäivä: {paiva.pvm} (id={paiva.id}), call {paiva.call_time}, wrap {paiva.wrap_arvio}")
        print(f"Aktiivisia tehtäviä: {len(tehtavat)} "
              f"(generoituja {sum(t.generoitu for t in tehtavat)})")
        print("Demokäyttäjät (email / salasana):")
        for email, _nimi, _rooli, salasana in DEMOKAYTTAJAT:
            print(f"  {email} / {salasana}")
        print("Valmis. Kokeile optimointia:")
        print(f"  POST /paivat/{paiva.id}/optimoi")


if __name__ == "__main__":
    asyncio.run(main())

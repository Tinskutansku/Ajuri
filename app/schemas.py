"""Pydantic v2 -skeemat. Jokaiselle perusdataentiteetille erikseen
Create-malli (syöte) ja Read-malli (vastaus, sisältää id:n)."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.models import HenkiloTyyppi, KayttajaRooli, SopimusTyyppi, TehtavaTyyppi

# ---------------------------------------------------------------------------
# Tuotanto
# ---------------------------------------------------------------------------


class TuotantoBase(BaseModel):
    nimi: str
    alkaa: date | None = None
    paattyy: date | None = None
    tuntihinta_eur: float = 22.0


class TuotantoCreate(TuotantoBase):
    pass


class TuotantoRead(TuotantoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    luotu: datetime


# ---------------------------------------------------------------------------
# Henkilo
# ---------------------------------------------------------------------------


class HenkiloBase(BaseModel):
    tyyppi: HenkiloTyyppi
    nimi: str
    roolinimi: str | None = None
    titteli: str | None = None
    puhelin: str | None = None
    osoite: str | None = None
    lat: float | None = None
    lon: float | None = None
    oletus_oma_auto: bool = False
    oletus_yksin: bool = False
    nouto_bufferi_min: int = 0
    max_etuajassa_min: int | None = Field(default=None, ge=0, le=240)
    huomiot: str | None = None
    aktiivinen: bool = True


class HenkiloCreate(HenkiloBase):
    tuotanto_id: int


class HenkiloRead(HenkiloBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int


# ---------------------------------------------------------------------------
# Kuski
# ---------------------------------------------------------------------------


class KuskiBase(BaseModel):
    nimi: str
    puhelin: str | None = None
    sopimus: SopimusTyyppi
    tuntihinta_eur: float | None = None
    koti_osoite: str | None = None
    koti_lat: float | None = None
    koti_lon: float | None = None
    pickup_bufferi_min: int = 0
    aktiivinen: bool = True


class KuskiCreate(KuskiBase):
    tuotanto_id: int


class KuskiRead(KuskiBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int


# ---------------------------------------------------------------------------
# Ajoneuvo
# ---------------------------------------------------------------------------


class AjoneuvoBase(BaseModel):
    nimi: str
    rekisteri: str | None = None
    mukavuuspaikat: int = 3
    max_paikat: int = 4
    osasto: str | None = None
    kaytossa_alkaen: date | None = None
    kaytossa_asti: date | None = None
    huomiot: str | None = None


class AjoneuvoCreate(AjoneuvoBase):
    tuotanto_id: int


class AjoneuvoRead(AjoneuvoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int


# ---------------------------------------------------------------------------
# Lokaatio
# ---------------------------------------------------------------------------


class LokaatioBase(BaseModel):
    nimi: str
    osoite: str | None = None
    lat: float | None = None
    lon: float | None = None
    ajo_ohjeet: str | None = None
    aktiivinen: bool = True


class LokaatioCreate(LokaatioBase):
    tuotanto_id: int


class LokaatioRead(LokaatioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int


class KayttoPaiva(BaseModel):
    """Vastaus GET /{resurssi}/{id}/kaytto: missä kuvauspäivissä
    henkilö/kuski/lokaatio on mukana (docs/tuotekartta.md, vaihe F)."""

    paiva_id: int
    pvm: date
    paiva_nro: str | None


# ---------------------------------------------------------------------------
# Kuvauspaiva
# ---------------------------------------------------------------------------


class KuvauspaivaBase(BaseModel):
    pvm: date
    paiva_nro: str | None = None
    call_time: time
    lounas: time | None = None
    wrap_arvio: time | None = None
    huomiot: str | None = None


class KuvauspaivaCreate(KuvauspaivaBase):
    tuotanto_id: int


class KuvauspaivaRead(KuvauspaivaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int


# ---------------------------------------------------------------------------
# PaivaLokaatio
# ---------------------------------------------------------------------------


class PaivaLokaatioBase(BaseModel):
    lokaatio_id: int
    jarjestys: int = 1
    siirtyma_klo: time | None = None


class PaivaLokaatioCreate(PaivaLokaatioBase):
    paiva_id: int


class PaivaLokaatioRead(PaivaLokaatioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paiva_id: int


# ---------------------------------------------------------------------------
# PaivaHenkilo
# ---------------------------------------------------------------------------


class PaivaHenkiloBase(BaseModel):
    henkilo_id: int
    oma_call: time | None = None
    oma_auto: bool = False
    ei_paluuta: bool = False
    siirtyy: bool = True
    siirtyma_klo: time | None = None
    huomiot: str | None = None


class PaivaHenkiloCreate(PaivaHenkiloBase):
    paiva_id: int


class PaivaHenkiloRead(PaivaHenkiloBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paiva_id: int


# ---------------------------------------------------------------------------
# PaivaKuski
# ---------------------------------------------------------------------------


class PaivaKuskiBase(BaseModel):
    kuski_id: int
    ajoneuvo_id: int | None = None
    tarjolla: bool = True
    vuoro_aikaisintaan: time | None = None
    vuoro_viimeistaan: time | None = None
    toteutunut_alku: time | None = None
    toteutunut_loppu: time | None = None


class PaivaKuskiCreate(PaivaKuskiBase):
    paiva_id: int


class PaivaKuskiRead(PaivaKuskiBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paiva_id: int


# ---------------------------------------------------------------------------
# Tehtava
# ---------------------------------------------------------------------------


class TehtavaBase(BaseModel):
    tyyppi: TehtavaTyyppi
    nimi: str
    henkilo_id: int | None = None
    henkiloita: int = 1
    mista_osoite: str
    mista_lat: float | None = None
    mista_lon: float | None = None
    mihin_osoite: str
    mihin_lat: float | None = None
    mihin_lon: float | None = None
    nouto_aikaisintaan: time | None = None
    nouto_viimeistaan: time | None = None
    perilla_aikaisintaan: time | None = None
    perilla_viimeistaan: time | None = None
    generoitu: bool = False
    aktiivinen: bool = True
    lukittu_kuski_id: int | None = None
    yksin: bool = False
    huomiot: str | None = None


class TehtavaCreate(TehtavaBase):
    paiva_id: int


class TehtavaRead(TehtavaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paiva_id: int


class TehtavaGenerointiVastaus(BaseModel):
    tehtavat: list[TehtavaRead]
    varoitus: str | None = None


# ---------------------------------------------------------------------------
# AjolistaVersio / Keikka (vain julkaisu/kuittaus-toiminnot, ei omaa CRUD:ia)
# ---------------------------------------------------------------------------


class AjolistaVersioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    paiva_id: int
    versio_nro: int
    luotu: datetime
    luoja_id: int | None
    kokonaiskustannus_eur: float | None
    julkaistu: bool
    tunniste: str | None
    kommentti: str | None


class KeikkaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    versio_id: int
    tehtava_id: int
    paiva_kuski_id: int
    nouto_klo: time
    jatto_klo: time
    jarjestys: int
    kasin_siirretty: bool
    kuitattu: bool


# ---------------------------------------------------------------------------
# Versiodiffi (ROADMAP J1, docs/tuotekartta.md vaihe J)
# ---------------------------------------------------------------------------


class DiffKeikka(BaseModel):
    """Yksi keikka diffissä. Keikat täsmätään versioiden välillä
    tehtava_id:n perusteella. `_a`-kentät ovat vanhasta versiosta, `_b`
    uudesta; uudella keikalla `_a`-kentät ovat None, poistuneella `_b`."""

    tehtava_id: int
    tehtava_nimi: str
    kuski_id_a: int | None = None
    kuski_nimi_a: str | None = None
    kuski_id_b: int | None = None
    kuski_nimi_b: str | None = None
    nouto_klo_a: time | None = None
    nouto_klo_b: time | None = None
    jatto_klo_a: time | None = None
    jatto_klo_b: time | None = None


class DiffKuski(BaseModel):
    """Kuskikohtainen keikkamäärän muutos ("Tiinalle +1 keikka")."""

    kuski_id: int
    kuski_nimi: str
    keikkoja_a: int
    keikkoja_b: int
    muutos: int


class VersioDiff(BaseModel):
    versio_a_id: int
    versio_b_id: int
    paiva_id: int
    siirtyneet: list[DiffKeikka]          # nouto- tai jättöaika muuttui
    kuskia_vaihtaneet: list[DiffKeikka]   # sama tehtävä, eri kuski
    uudet: list[DiffKeikka]               # vain versiossa b
    poistuneet: list[DiffKeikka]          # vain versiossa a
    ennallaan_lkm: int                    # sama kuski ja samat ajat
    kuskit: list[DiffKuski]               # vain kuskit, joiden keikkamäärä muuttui
    kokonaiskustannus_a_eur: float | None
    kokonaiskustannus_b_eur: float | None
    kustannusmuutos_eur: float | None     # b - a; None jos kumpi tahansa puuttuu


# ---------------------------------------------------------------------------
# Optimointi (docs/optimoija-spec.md §1)
# ---------------------------------------------------------------------------


class OptimointiPyynto(BaseModel):
    aikaraja_s: int = 15
    max_etuajassa_min: int = 30
    max_kyytiaika_lisa_min: int = 25
    nyt: str | None = None
    pohjaversio_id: int | None = None
    skenaariot: bool = True


class KeikkaVastaus(BaseModel):
    keikka_id: int
    tehtava_id: int
    nimi: str
    nouto_klo: str
    jatto_klo: str
    mista: str
    mihin: str
    kuitattu: bool
    lukittu: bool


class KuskinAjolista(BaseModel):
    paiva_kuski_id: int
    nimi: str
    sopimus: SopimusTyyppi
    vuoro_alku: str
    vuoro_loppu: str
    kesto_min: int
    lisakustannus_eur: float
    keikat: list[KeikkaVastaus]


class Sijoittamaton(BaseModel):
    tehtava_id: int
    nimi: str
    syy: str
    selite: str


class Skenaario(BaseModel):
    kuskeja_tarjolla: int
    kuskeja_kaytossa: int
    kustannus_eur: float | None
    ratkeaa: bool
    halvin: bool


class OptimoinninTila(BaseModel):
    """GET /paivat/{id}/optimointi: onko päivän optimointi kesken ja mikä on
    päivän viimeisin tallennettu ajolistaversio. Ei kustannuksia, joten
    roolisuodatusta ei tarvita."""

    paiva_id: int
    kaynnissa: bool
    viimeisin_versio_id: int | None


class OptimointiVastaus(BaseModel):
    versio_id: int
    versio_nro: int
    kokonaiskustannus_eur: float
    kuskit: list[KuskinAjolista]
    sijoittamatta: list[Sijoittamaton]
    skenaariot: list[Skenaario] | None = None


# ---------------------------------------------------------------------------
# Geokoodaus (docs/tuotekartta.md, vaihe E)
# ---------------------------------------------------------------------------


class GeokoodausTulos(BaseModel):
    henkilot_paivitetty: int
    henkilot_epaonnistui: int
    kuskit_paivitetty: int
    kuskit_epaonnistui: int
    lokaatiot_paivitetty: int
    lokaatiot_epaonnistui: int
    jaljella: int  # koordinaatittomia rivejä joita EI yritetty tässä kutsussa


# ---------------------------------------------------------------------------
# Kirjautuminen (app/routers/auth.py)
# ---------------------------------------------------------------------------


class KirjautumisPyynto(BaseModel):
    email: str = Field(min_length=1, max_length=200)
    salasana: str = Field(min_length=1, max_length=200)


class KayttajaRead(BaseModel):
    """Käyttäjä ilman salasana-hashia."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int
    email: str
    nimi: str
    rooli: KayttajaRooli
    kuski_id: int | None = None
    aktiivinen: bool
    viimeksi_kirjautunut: datetime | None = None


class TokenVastaus(BaseModel):
    access_token: str
    token_type: str = "bearer"
    voimassa_s: int
    kayttaja: KayttajaRead

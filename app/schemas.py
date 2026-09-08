"""Pydantic v2 -skeemat. Jokaiselle perusdataentiteetille erikseen
Create-malli (syöte) ja Read-malli (vastaus, sisältää id:n)."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict

from app.models import HenkiloTyyppi, SopimusTyyppi, TehtavaTyyppi

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
    huomiot: str | None = None


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


class LokaatioCreate(LokaatioBase):
    tuotanto_id: int


class LokaatioRead(LokaatioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tuotanto_id: int


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


class OptimointiVastaus(BaseModel):
    versio_id: int
    versio_nro: int
    kokonaiskustannus_eur: float
    kuskit: list[KuskinAjolista]
    sijoittamatta: list[Sijoittamaton]
    skenaariot: list[Skenaario] | None = None

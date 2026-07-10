"""Pydantic v2 -skeemat. Jokaiselle perusdataentiteetille erikseen
Create-malli (syöte) ja Read-malli (vastaus, sisältää id:n)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models import HenkiloTyyppi, SopimusTyyppi

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

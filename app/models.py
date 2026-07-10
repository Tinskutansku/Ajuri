"""
AJOLISTA — tietokantamallit (SQLAlchemy 2.0, PostgreSQL)
=========================================================
Rakenne kolmessa kerroksessa:
  1) Tuotannon perusdata: henkilöt, kuskit, autot, lokaatiot (harvoin muuttuu)
  2) Päiväkohtainen data: kuvauspäivä, osallistujat, tarjolla olevat kuskit, tehtävät
  3) Tulokset versioituna: ajolistaversiot ja keikat

Alembic-alustus:
  alembic init alembic
  # alembic/env.py: target_metadata = Base.metadata
  alembic revision --autogenerate -m "init"
  alembic upgrade head
"""

from __future__ import annotations
import enum
from datetime import date, datetime, time
from sqlalchemy import (
    ForeignKey, String, Text, Enum, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enumit
# ---------------------------------------------------------------------------

class HenkiloTyyppi(enum.Enum):
    CAST = "cast"
    CREW = "crew"

class SopimusTyyppi(enum.Enum):
    KUUKAUSI = "kuukausi"     # 37,5 h/vko, peruspalkka maksettu -> vain ylityöt maksavat
    PAIVA = "paiva"           # päiväpalkka = aina 8 h könttä
    TUNTI = "tunti"           # extra, 4 h minimi, portaat 8 h / 10 h

class TehtavaTyyppi(enum.Enum):
    HENKILO = "henkilo"
    SIIRTYMA = "siirtyma"
    PALUU = "paluu"
    TAVARA = "tavara"         # kortit, lounas, lämpölaatikot...

class KayttajaRooli(enum.Enum):
    TUOTANTO = "tuotanto"     # näkee kustannukset, muokkaa kaikkea
    KOORDI = "koordi"         # muokkaa ajolistoja, näkee kustannukset
    KUSKI = "kuski"           # näkee vain oman ajolistansa, ei kustannuksia


# ---------------------------------------------------------------------------
# 1) Tuotannon perusdata
# ---------------------------------------------------------------------------

class Tuotanto(Base):
    __tablename__ = "tuotanto"
    id: Mapped[int] = mapped_column(primary_key=True)
    nimi: Mapped[str] = mapped_column(String(200))
    alkaa: Mapped[date | None]
    paattyy: Mapped[date | None]
    tuntihinta_eur: Mapped[float] = mapped_column(default=22.0)   # kuskin oletustuntihinta
    luotu: Mapped[datetime] = mapped_column(server_default=func.now())

    henkilot: Mapped[list["Henkilo"]] = relationship(back_populates="tuotanto")
    kuskit: Mapped[list["Kuski"]] = relationship(back_populates="tuotanto")
    ajoneuvot: Mapped[list["Ajoneuvo"]] = relationship(back_populates="tuotanto")
    lokaatiot: Mapped[list["Lokaatio"]] = relationship(back_populates="tuotanto")
    paivat: Mapped[list["Kuvauspaiva"]] = relationship(back_populates="tuotanto")


class Kayttaja(Base):
    __tablename__ = "kayttaja"
    id: Mapped[int] = mapped_column(primary_key=True)
    tuotanto_id: Mapped[int] = mapped_column(ForeignKey("tuotanto.id"))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    nimi: Mapped[str] = mapped_column(String(200))
    rooli: Mapped[KayttajaRooli] = mapped_column(Enum(KayttajaRooli))
    # rooli KUSKI: linkki kuski-tauluun, jotta näkee vain oman listansa
    kuski_id: Mapped[int | None] = mapped_column(ForeignKey("kuski.id"))


class Henkilo(Base):
    """Kuskattava henkilö: näyttelijä (roolinimi) tai työryhmäläinen (titteli)."""
    __tablename__ = "henkilo"
    id: Mapped[int] = mapped_column(primary_key=True)
    tuotanto_id: Mapped[int] = mapped_column(ForeignKey("tuotanto.id"))
    tyyppi: Mapped[HenkiloTyyppi] = mapped_column(Enum(HenkiloTyyppi))
    nimi: Mapped[str] = mapped_column(String(200))
    roolinimi: Mapped[str | None] = mapped_column(String(200))     # cast
    titteli: Mapped[str | None] = mapped_column(String(200))       # crew
    puhelin: Mapped[str | None] = mapped_column(String(50))
    osoite: Mapped[str | None] = mapped_column(String(300))        # nouto-osoite (hotelli/koti)
    lat: Mapped[float | None]                                      # geokoodattu kerran talteen
    lon: Mapped[float | None]
    oletus_oma_auto: Mapped[bool] = mapped_column(default=False)
    oletus_yksin: Mapped[bool] = mapped_column(default=False)      # ei kimppakyytejä
    huomiot: Mapped[str | None] = mapped_column(Text)

    tuotanto: Mapped["Tuotanto"] = relationship(back_populates="henkilot")


class Kuski(Base):
    __tablename__ = "kuski"
    id: Mapped[int] = mapped_column(primary_key=True)
    tuotanto_id: Mapped[int] = mapped_column(ForeignKey("tuotanto.id"))
    nimi: Mapped[str] = mapped_column(String(200))
    puhelin: Mapped[str | None] = mapped_column(String(50))
    sopimus: Mapped[SopimusTyyppi] = mapped_column(Enum(SopimusTyyppi))
    tuntihinta_eur: Mapped[float | None]                           # None -> tuotannon oletus
    koti_osoite: Mapped[str | None] = mapped_column(String(300))
    koti_lat: Mapped[float | None]
    koti_lon: Mapped[float | None]

    tuotanto: Mapped["Tuotanto"] = relationship(back_populates="kuskit")


class Ajoneuvo(Base):
    """Autolista: myös osastojen omat autot hätävarakapasiteettina."""
    __tablename__ = "ajoneuvo"
    id: Mapped[int] = mapped_column(primary_key=True)
    tuotanto_id: Mapped[int] = mapped_column(ForeignKey("tuotanto.id"))
    nimi: Mapped[str] = mapped_column(String(200))                 # "Farmari ABC-123"
    rekisteri: Mapped[str | None] = mapped_column(String(20))
    mukavuuspaikat: Mapped[int] = mapped_column(default=3)         # optimoijan kapasiteetti
    max_paikat: Mapped[int] = mapped_column(default=4)             # hätävara, vaatii hyväksynnän
    osasto: Mapped[str | None] = mapped_column(String(100))        # NULL = kuljetusauto
    kaytossa_alkaen: Mapped[date | None]                           # autolistan jaksot
    kaytossa_asti: Mapped[date | None]
    huomiot: Mapped[str | None] = mapped_column(Text)

    tuotanto: Mapped["Tuotanto"] = relationship(back_populates="ajoneuvot")


class Lokaatio(Base):
    __tablename__ = "lokaatio"
    id: Mapped[int] = mapped_column(primary_key=True)
    tuotanto_id: Mapped[int] = mapped_column(ForeignKey("tuotanto.id"))
    nimi: Mapped[str] = mapped_column(String(200))                 # "LOC 1, Hamarin talo"
    osoite: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    ajo_ohjeet: Mapped[str | None] = mapped_column(Text)           # "tarkemmat ohjeet järkältä"

    tuotanto: Mapped["Tuotanto"] = relationship(back_populates="lokaatiot")


# ---------------------------------------------------------------------------
# 2) Päiväkohtainen data
# ---------------------------------------------------------------------------

class Kuvauspaiva(Base):
    __tablename__ = "kuvauspaiva"
    id: Mapped[int] = mapped_column(primary_key=True)
    tuotanto_id: Mapped[int] = mapped_column(ForeignKey("tuotanto.id"))
    pvm: Mapped[date]
    paiva_nro: Mapped[str | None] = mapped_column(String(20))      # "22/49"
    call_time: Mapped[time]
    lounas: Mapped[time | None]
    wrap_arvio: Mapped[time | None]
    huomiot: Mapped[str | None] = mapped_column(Text)

    tuotanto: Mapped["Tuotanto"] = relationship(back_populates="paivat")
    lokaatiot: Mapped[list["PaivaLokaatio"]] = relationship(back_populates="paiva")
    henkilot: Mapped[list["PaivaHenkilo"]] = relationship(back_populates="paiva")
    kuskit: Mapped[list["PaivaKuski"]] = relationship(back_populates="paiva")
    tehtavat: Mapped[list["Tehtava"]] = relationship(back_populates="paiva")
    versiot: Mapped[list["AjolistaVersio"]] = relationship(back_populates="paiva")
    __table_args__ = (UniqueConstraint("tuotanto_id", "pvm"),)


class PaivaLokaatio(Base):
    """Päivän lokaatiot järjestyksessä + siirtymän kellonaika."""
    __tablename__ = "paiva_lokaatio"
    id: Mapped[int] = mapped_column(primary_key=True)
    paiva_id: Mapped[int] = mapped_column(ForeignKey("kuvauspaiva.id"))
    lokaatio_id: Mapped[int] = mapped_column(ForeignKey("lokaatio.id"))
    jarjestys: Mapped[int] = mapped_column(default=1)
    siirtyma_klo: Mapped[time | None]                              # milloin tänne siirrytään

    paiva: Mapped["Kuvauspaiva"] = relationship(back_populates="lokaatiot")
    lokaatio: Mapped["Lokaatio"] = relationship()


class PaivaHenkilo(Base):
    """Kuka on mukana tänä päivänä ja millä ehdoilla. Perusdata ei muutu."""
    __tablename__ = "paiva_henkilo"
    id: Mapped[int] = mapped_column(primary_key=True)
    paiva_id: Mapped[int] = mapped_column(ForeignKey("kuvauspaiva.id"))
    henkilo_id: Mapped[int] = mapped_column(ForeignKey("henkilo.id"))
    oma_call: Mapped[time | None]                                  # NULL = yleinen call
    oma_auto: Mapped[bool] = mapped_column(default=False)
    ei_paluuta: Mapped[bool] = mapped_column(default=False)
    siirtyy: Mapped[bool] = mapped_column(default=True)
    huomiot: Mapped[str | None] = mapped_column(Text)              # "muistuta matkatavarat"

    paiva: Mapped["Kuvauspaiva"] = relationship(back_populates="henkilot")
    henkilo: Mapped["Henkilo"] = relationship()
    __table_args__ = (UniqueConstraint("paiva_id", "henkilo_id"),)


class PaivaKuski(Base):
    """Kuka kuskaa tänään, millä autolla — ja toteutuneet tunnit viikkosaldoon."""
    __tablename__ = "paiva_kuski"
    id: Mapped[int] = mapped_column(primary_key=True)
    paiva_id: Mapped[int] = mapped_column(ForeignKey("kuvauspaiva.id"))
    kuski_id: Mapped[int] = mapped_column(ForeignKey("kuski.id"))
    ajoneuvo_id: Mapped[int | None] = mapped_column(ForeignKey("ajoneuvo.id"))
    tarjolla: Mapped[bool] = mapped_column(default=True)
    vuoro_aikaisintaan: Mapped[time | None]                        # esim. toimistohommia aamulla
    vuoro_viimeistaan: Mapped[time | None]
    toteutunut_alku: Mapped[time | None]                           # kirjataan päivän päätteeksi
    toteutunut_loppu: Mapped[time | None]                          # -> 37,5 h/vko -seuranta

    paiva: Mapped["Kuvauspaiva"] = relationship(back_populates="kuskit")
    kuski: Mapped["Kuski"] = relationship()
    ajoneuvo: Mapped["Ajoneuvo"] = relationship()
    __table_args__ = (UniqueConstraint("paiva_id", "kuski_id"),)


class Tehtava(Base):
    """Kuljetustehtävä: nouto -> jättö aikaikkunoilla. Generoitu tai käsin."""
    __tablename__ = "tehtava"
    id: Mapped[int] = mapped_column(primary_key=True)
    paiva_id: Mapped[int] = mapped_column(ForeignKey("kuvauspaiva.id"))
    tyyppi: Mapped[TehtavaTyyppi] = mapped_column(Enum(TehtavaTyyppi))
    nimi: Mapped[str] = mapped_column(String(300))
    henkilo_id: Mapped[int | None] = mapped_column(ForeignKey("henkilo.id"))  # yhteystietoihin
    henkiloita: Mapped[int] = mapped_column(default=1)             # 0 = tavara
    # osoitteet snapshotteina, jotta optimointi ei riipu perusdatan muutoksista:
    mista_osoite: Mapped[str] = mapped_column(String(300))
    mista_lat: Mapped[float | None]
    mista_lon: Mapped[float | None]
    mihin_osoite: Mapped[str] = mapped_column(String(300))
    mihin_lat: Mapped[float | None]
    mihin_lon: Mapped[float | None]
    nouto_aikaisintaan: Mapped[time | None]
    nouto_viimeistaan: Mapped[time | None]
    perilla_aikaisintaan: Mapped[time | None]
    perilla_viimeistaan: Mapped[time | None]
    generoitu: Mapped[bool] = mapped_column(default=False)         # softan luonnos vs käsin
    lukittu_kuski_id: Mapped[int | None] = mapped_column(ForeignKey("kuski.id"))  # "Tiina hakee aina X:n"
    yksin: Mapped[bool] = mapped_column(default=False)             # ei kimppakyytiä
    huomiot: Mapped[str | None] = mapped_column(Text)              # "lento laskeutuu 15:25"

    paiva: Mapped["Kuvauspaiva"] = relationship(back_populates="tehtavat")


# ---------------------------------------------------------------------------
# 3) Tulokset versioituna
# ---------------------------------------------------------------------------

class AjolistaVersio(Base):
    """Jokainen optimointiajo = uusi versio. Uudelleenoptimointi ei tuhoa mitään."""
    __tablename__ = "ajolista_versio"
    id: Mapped[int] = mapped_column(primary_key=True)
    paiva_id: Mapped[int] = mapped_column(ForeignKey("kuvauspaiva.id"))
    versio_nro: Mapped[int]
    luotu: Mapped[datetime] = mapped_column(server_default=func.now())
    luoja_id: Mapped[int | None] = mapped_column(ForeignKey("kayttaja.id"))
    kokonaiskustannus_eur: Mapped[float | None]                    # vain tuotanto/koordi näkee
    julkaistu: Mapped[bool] = mapped_column(default=False)         # jaettu kuskeille
    kommentti: Mapped[str | None] = mapped_column(Text)            # "Näyttelijä X sairastui, v2"

    paiva: Mapped["Kuvauspaiva"] = relationship(back_populates="versiot")
    keikat: Mapped[list["Keikka"]] = relationship(back_populates="versio")
    __table_args__ = (UniqueConstraint("paiva_id", "versio_nro"),)


class Keikka(Base):
    """Yksi rivi ajolistassa: tehtävä sijoitettuna kuskille aikoineen."""
    __tablename__ = "keikka"
    id: Mapped[int] = mapped_column(primary_key=True)
    versio_id: Mapped[int] = mapped_column(ForeignKey("ajolista_versio.id"))
    tehtava_id: Mapped[int] = mapped_column(ForeignKey("tehtava.id"))
    paiva_kuski_id: Mapped[int] = mapped_column(ForeignKey("paiva_kuski.id"))
    nouto_klo: Mapped[time]
    jatto_klo: Mapped[time]
    jarjestys: Mapped[int]                                         # kuskin reitin järjestysnro
    kasin_siirretty: Mapped[bool] = mapped_column(default=False)   # koordi ohitti optimoijan
    kuitattu: Mapped[bool] = mapped_column(default=False)          # ajettu -> lukitaan reoptimoinnissa

    versio: Mapped["AjolistaVersio"] = relationship(back_populates="keikat")
    tehtava: Mapped["Tehtava"] = relationship()
    paiva_kuski: Mapped["PaivaKuski"] = relationship()


# ---------------------------------------------------------------------------
# 4) Ajoaikavälimuisti (optimoijaservice)
# ---------------------------------------------------------------------------

class Matka(Base):
    """Reititys-API:sta haettujen ajoaikojen välimuisti pistepareittain.

    Koordinaatit pyöristetään 4 desimaaliin (≈10 m) ennen tallennusta,
    jotta samaa osoitetta ei kysytä API:sta uudestaan pienten
    liukulukuerojen takia.
    """
    __tablename__ = "matka"
    id: Mapped[int] = mapped_column(primary_key=True)
    mista_lat: Mapped[float]
    mista_lon: Mapped[float]
    mihin_lat: Mapped[float]
    mihin_lon: Mapped[float]
    ajoaika_s: Mapped[int]
    matka_m: Mapped[float]
    haettu: Mapped[datetime] = mapped_column(server_default=func.now())
    lahde: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("mista_lat", "mista_lon", "mihin_lat", "mihin_lon"),
    )

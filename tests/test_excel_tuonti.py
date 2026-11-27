"""O1: Excel-tuonti rekisteriin esikatselulla.

Esimerkkitiedostot ovat tests/data/-hakemistossa (luotu skriptillä
tests/data/luo_tuontitiedostot.py). Tiedosto lähetetään pyynnön runkona.
"""

import io
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.models import Henkilo, HenkiloTyyppi, KayttajaRooli, Tuotanto
from app.rooli import EI_OIKEUTTA_MUOKATA
from app.services import excel_tuonti
from tests.conftest import FakeGeocoder

DATA = Path(__file__).parent / "data"
XLSX = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


def _tiedosto(nimi: str) -> bytes:
    return (DATA / nimi).read_bytes()


def _kirja(rivit: list[list]) -> bytes:
    kirja = Workbook()
    for rivi in rivit:
        kirja.active.append(rivi)
    puskuri = io.BytesIO()
    kirja.save(puskuri)
    return puskuri.getvalue()


async def _esikatsele(client, tuotanto_id: int, sisalto: bytes, **kw):
    return await client.post(f"/tuotannot/{tuotanto_id}/tuonti/esikatselu", content=sisalto, headers=XLSX, **kw)


async def _tuo(client, tuotanto_id: int, sisalto: bytes, **kw):
    return await client.post(f"/tuotannot/{tuotanto_id}/tuonti", content=sisalto, headers=XLSX, **kw)


# ---------------------------------------------------------------------------
# Esikatselu
# ---------------------------------------------------------------------------


async def test_esikatselu_tulkitsee_rivit_ja_sarakkeet(client, tuotanto_id):
    vastaus = await _esikatsele(client, tuotanto_id, _tiedosto("henkilot_ok.xlsx"))
    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()

    assert data["sarakkeet"] == [
        {"otsikko": "Tyyppi", "kentta": "tyyppi"},
        {"otsikko": "Nimi", "kentta": "nimi"},
        {"otsikko": "Rooli", "kentta": "roolinimi"},
        {"otsikko": "Titteli", "kentta": "titteli"},
        {"otsikko": "Puhelin", "kentta": "puhelin"},
        {"otsikko": "Osoite", "kentta": "osoite"},
        {"otsikko": "Huomiot", "kentta": "huomiot"},
        {"otsikko": "Allergiat", "kentta": None},   # tuntematon sarake ohitetaan
    ]
    assert data["kelvollisia"] == 4
    assert data["virheellisia"] == 0

    rivit = {r["rivi"]: r for r in data["rivit"]}
    assert set(rivit) == {2, 3, 4, 6}  # rivi 5 on tyhjä

    aino = rivit[2]["henkilo"]
    assert aino["tyyppi"] == "cast"
    assert aino["roolinimi"] == "Liisa"
    assert aino["puhelin"] == "040 123 4567"

    bertta = rivit[3]["henkilo"]
    assert bertta["tyyppi"] == "crew"              # "Työryhmä" tunnistetaan
    assert bertta["puhelin"] == "401234567"        # luku tekstiksi ilman ".0"

    # Tyyppi puuttuu: roolinimi -> cast, muuten crew, ja siitä varoitus
    assert rivit[4]["henkilo"]["tyyppi"] == "crew"
    assert rivit[6]["henkilo"]["tyyppi"] == "cast"
    assert any("Tyyppi puuttui" in v for v in rivit[4]["varoitukset"])

    # Kaavaa ei suoriteta eikä tallenneta tekstinä
    assert rivit[6]["henkilo"]["huomiot"] is None


async def test_esikatselu_ei_tallenna_eika_geokoodaa(client, tuotanto_id, db_session):
    from app.main import app
    from app.services.geocoder_client import get_geocoder_client

    geocoder = FakeGeocoder()
    app.dependency_overrides[get_geocoder_client] = lambda: geocoder
    vastaus = await _esikatsele(client, tuotanto_id, _tiedosto("henkilot_ok.xlsx"))
    assert vastaus.status_code == 200
    assert (await db_session.execute(select(Henkilo))).scalars().all() == []
    assert geocoder.kutsut == []


async def test_esikatselu_virheet_riveittain(client, tuotanto_id):
    vastaus = await _esikatsele(client, tuotanto_id, _tiedosto("henkilot_virheet.xlsx"))
    assert vastaus.status_code == 200, vastaus.text
    data = vastaus.json()
    assert data["kelvollisia"] == 1
    assert data["virheellisia"] == 4

    rivit = {r["rivi"]: r for r in data["rivit"]}
    assert rivit[2]["virheet"] == []
    assert rivit[2]["henkilo"]["nimi"] == "Eero Kelpo"
    assert "Tuntematon tyyppi" in rivit[3]["virheet"][0]
    assert rivit[4]["virheet"] == ["Nimi puuttuu."]
    assert "nimi" in rivit[5]["virheet"][0] and "200" in rivit[5]["virheet"][0]
    assert "puhelin" in rivit[6]["virheet"][0] and "50" in rivit[6]["virheet"][0]
    for nro in (3, 4, 5, 6):
        assert rivit[nro]["henkilo"] is None


async def test_esikatselu_varoittaa_samannimisista(client, tuotanto_id, db_session):
    db_session.add(Henkilo(tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CREW, nimi="Bertta Valo"))
    await db_session.commit()
    sisalto = _kirja([["Nimi"], ["bertta  valo"], ["Uusi Ihminen"], ["Uusi Ihminen"]])

    rivit = {r["rivi"]: r for r in (await _esikatsele(client, tuotanto_id, sisalto)).json()["rivit"]}
    assert "Rekisterissä on jo samanniminen henkilö." in rivit[2]["varoitukset"]
    assert rivit[3]["varoitukset"] == ["Tyyppi puuttui, tulkittu: crew."]
    assert "Sama nimi on myös rivillä 3." in rivit[4]["varoitukset"]


async def test_otsikkorivi_voi_olla_tyhjien_rivien_jalkeen(client, tuotanto_id):
    sisalto = _kirja([[None], ["  NIMI  ", "puh."], ["Jaana", "050 5"]])
    data = (await _esikatsele(client, tuotanto_id, sisalto)).json()
    assert data["rivit"][0]["rivi"] == 3
    assert data["rivit"][0]["henkilo"]["puhelin"] == "050 5"


# ---------------------------------------------------------------------------
# Koko tiedoston hylkäys
# ---------------------------------------------------------------------------


async def test_puuttuva_pakollinen_sarake(client, tuotanto_id):
    vastaus = await _esikatsele(client, tuotanto_id, _tiedosto("puuttuva_sarake.xlsx"))
    assert vastaus.status_code == 422
    assert "Pakollinen sarake puuttuu: nimi" in vastaus.json()["detail"]
    assert "Etunimi" in vastaus.json()["detail"]


@pytest.mark.parametrize("nimi", ["rikki.xlsx", "ei_excel.xlsx", "word.xlsx"])
async def test_rikkinainen_tai_muu_tiedosto_hylataan(client, tuotanto_id, nimi):
    for reitti in (_esikatsele, _tuo):
        vastaus = await reitti(client, tuotanto_id, _tiedosto(nimi))
        assert vastaus.status_code == 422, (nimi, vastaus.text)
        assert "Excel" in vastaus.json()["detail"]


async def test_tyhja_runko_hylataan(client, tuotanto_id):
    vastaus = await _esikatsele(client, tuotanto_id, b"")
    assert vastaus.status_code == 422
    assert vastaus.json()["detail"] == "Tiedosto on tyhjä."


async def test_zip_pommi_hylataan_ennen_openpyxlaa(client, tuotanto_id, monkeypatch):
    def ei_saa_kutsua(_):
        raise AssertionError("openpyxl avasi zip-pommin")

    monkeypatch.setattr(excel_tuonti, "_avaa_tyokirja", ei_saa_kutsua)
    for reitti in (_esikatsele, _tuo):
        vastaus = await reitti(client, tuotanto_id, _tiedosto("zip_pommi.xlsx"))
        assert vastaus.status_code == 422
        assert vastaus.json()["detail"] == "Tiedosto on purettuna liian suuri."


async def test_liikaa_zip_osia_hylataan(client, tuotanto_id):
    puskuri = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_tiedosto("henkilot_ok.xlsx"))) as lahde, \
            zipfile.ZipFile(puskuri, "w", zipfile.ZIP_DEFLATED) as kohde:
        for osa in lahde.infolist():
            kohde.writestr(osa, lahde.read(osa))
        for i in range(excel_tuonti.ZIP_TIEDOSTOT_MAX):
            kohde.writestr(f"xl/media/{i}.bin", b"x")
    vastaus = await _esikatsele(client, tuotanto_id, puskuri.getvalue())
    assert vastaus.status_code == 422
    assert "liian monta osaa" in vastaus.json()["detail"]


@pytest.mark.parametrize("koodaus", ["utf-8", "utf-16"])
async def test_xml_entiteetit_hylataan(client, tuotanto_id, koodaus):
    """Billion laughs / XXE: DTD:tä ei ole oikeassa xlsx:ssä koskaan."""
    puskuri = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(_tiedosto("henkilot_ok.xlsx"))) as lahde, \
            zipfile.ZipFile(puskuri, "w", zipfile.ZIP_DEFLATED) as kohde:
        for osa in lahde.infolist():
            data = lahde.read(osa)
            if osa.filename == "xl/worksheets/sheet1.xml":
                data = ('<!DOCTYPE x [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
                        + data.decode()).encode(koodaus)
            kohde.writestr(osa, data)
    vastaus = await _esikatsele(client, tuotanto_id, puskuri.getvalue())
    assert vastaus.status_code == 422
    assert "XML" in vastaus.json()["detail"]


async def test_liian_suuri_tiedosto_413(client, tuotanto_id):
    sisalto = b"PK\x03\x04" + b"\0" * excel_tuonti.TIEDOSTO_MAX_TAVUA
    vastaus = await _esikatsele(client, tuotanto_id, sisalto)
    assert vastaus.status_code == 413
    assert "2 Mt" in vastaus.json()["detail"]


async def test_liikaa_riveja_hylataan(client, tuotanto_id):
    rivit = [["Nimi"]] + [[f"Henkilö {i}"] for i in range(excel_tuonti.RIVIT_MAX + 1)]
    vastaus = await _esikatsele(client, tuotanto_id, _kirja(rivit))
    assert vastaus.status_code == 422
    assert "liian monta riviä" in vastaus.json()["detail"]

    # Täsmälleen raja kelpaa
    vastaus = await _esikatsele(client, tuotanto_id, _kirja(rivit[:-1]))
    assert vastaus.status_code == 200
    assert vastaus.json()["kelvollisia"] == excel_tuonti.RIVIT_MAX


# ---------------------------------------------------------------------------
# Tallennus
# ---------------------------------------------------------------------------


async def test_tuonti_tallentaa_kelvolliset_ja_ohittaa_virheelliset(client, tuotanto_id, db_session):
    vastaus = await _tuo(client, tuotanto_id, _tiedosto("henkilot_virheet.xlsx"))
    assert vastaus.status_code == 201, vastaus.text
    assert vastaus.json() == {"tallennettu": 1, "ohitetut_rivit": [3, 4, 5, 6], "geokoodaamatta": 0}

    henkilot = (await db_session.execute(select(Henkilo))).scalars().all()
    assert [(h.nimi, h.tyyppi, h.puhelin, h.tuotanto_id, h.aktiivinen) for h in henkilot] == [
        ("Eero Kelpo", HenkiloTyyppi.CREW, "050 1", tuotanto_id, True),
    ]


async def test_tuonti_ei_geokoodaa_vaan_jattaa_joukkoreitille(client, tuotanto_id, db_session):
    from app.main import app
    from app.services.geocoder_client import get_geocoder_client

    geocoder = FakeGeocoder({"Mannerheimintie 1, Helsinki": (60.17, 24.94)})
    app.dependency_overrides[get_geocoder_client] = lambda: geocoder

    vastaus = await _tuo(client, tuotanto_id, _tiedosto("henkilot_ok.xlsx"))
    assert vastaus.status_code == 201
    assert vastaus.json() == {"tallennettu": 4, "ohitetut_rivit": [], "geokoodaamatta": 3}
    assert geocoder.kutsut == []

    henkilot = (await db_session.execute(select(Henkilo).order_by(Henkilo.id))).scalars().all()
    assert [h.nimi for h in henkilot] == ["Aino Näyttelijä", "Bertta Valo", "Cecilia Rooliton", "Daniel Rooli"]
    assert all(h.lat is None and h.lon is None for h in henkilot)

    # Normaali joukkogeokoodaus täydentää tuodut osoitteet
    tulos = (await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa")).json()
    assert tulos["henkilot_paivitetty"] == 1
    assert tulos["henkilot_epaonnistui"] == 2
    await db_session.refresh(henkilot[0])
    assert (henkilot[0].lat, henkilot[0].lon) == (60.17, 24.94)


async def test_tuonti_tuotu_henkilo_nakyy_listauksessa(client, tuotanto_id):
    await _tuo(client, tuotanto_id, _tiedosto("henkilot_ok.xlsx"))
    nimet = [h["nimi"] for h in (await client.get("/henkilot")).json()]
    assert "Aino Näyttelijä" in nimet


# ---------------------------------------------------------------------------
# Oikeudet
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("polku", ["/tuonti/esikatselu", "/tuonti"])
async def test_kuski_ei_saa_tuoda(client, tuotanto_id, kuski_otsakkeet, polku):
    vastaus = await client.post(
        f"/tuotannot/{tuotanto_id}{polku}", content=_tiedosto("henkilot_ok.xlsx"),
        headers=XLSX | kuski_otsakkeet,
    )
    assert vastaus.status_code == 403
    assert vastaus.json()["detail"] == EI_OIKEUTTA_MUOKATA


async def test_koordi_saa_tuoda(client, tuotanto_id, koordi_otsakkeet):
    vastaus = await client.post(
        f"/tuotannot/{tuotanto_id}/tuonti", content=_tiedosto("henkilot_ok.xlsx"),
        headers=XLSX | koordi_otsakkeet,
    )
    assert vastaus.status_code == 201


@pytest.mark.parametrize("polku", ["/tuonti/esikatselu", "/tuonti"])
async def test_toisen_tuotannon_tuonti_404(client, db_session, polku):
    toinen = Tuotanto(nimi="Toinen")
    db_session.add(toinen)
    await db_session.commit()

    vastaus = await client.post(
        f"/tuotannot/{toinen.id}{polku}", content=_tiedosto("henkilot_ok.xlsx"), headers=XLSX,
    )
    assert vastaus.status_code == 404
    assert (await db_session.execute(select(Henkilo))).scalars().all() == []

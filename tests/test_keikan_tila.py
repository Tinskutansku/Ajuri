"""N3: "Kyydissä" / "Perillä" -kuittaukset (Tanjan päätös issuessa #38, A).

POST /keikat/{id}/tila. KUSKI saa kuitata vain oman keikkansa julkaistussa
versiossa ja vain eteenpäin. KOORDI ja TUOTANTO saavat myös perua.
Uudelleenoptimointi kopioi tilan uuteen versioon ja lukitsee kuitatun keikan.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import update

from app.models import KayttajaRooli, Keikka, KeikkaTila
from app.rooli import EI_OIKEUTTA_MUOKATA
from tests.test_kuski_pois_pelista import _keikka, _reoptimoi
from tests.test_kuski_pois_pelista import _seed as _seed_reoptimointi
from tests.test_kuskin_omat_keikat import _seed


async def _aseta(client, keikka_id: int, tila: str, otsakkeet=None):
    return await client.post(f"/keikat/{keikka_id}/tila", json={"tila": tila}, headers=otsakkeet or {})


@pytest.fixture
async def data(db_session):
    return await _seed(db_session)


@pytest.fixture
async def tiina(kirjaudu, data):
    return await kirjaudu(KayttajaRooli.KUSKI, kuski_id=data["tiina"])


# ---------------------------------------------------------------------------
# Kuski kuittaa oman keikkansa
# ---------------------------------------------------------------------------


async def test_kuski_kuittaa_kyydissa_ja_perilla(client, data, tiina):
    ennen = datetime.now(UTC).replace(tzinfo=None)

    vastaus = await _aseta(client, data["v1_tiina_1"], "kyydissa", tiina)
    assert vastaus.status_code == 200, vastaus.text
    k = vastaus.json()
    assert k["tila"] == "kyydissa"
    assert datetime.fromisoformat(k["kyydissa_klo"]) >= ennen
    assert k["perilla_klo"] is None
    assert k["kuitattu"] is False

    vastaus = await _aseta(client, data["v1_tiina_1"], "perilla", tiina)
    assert vastaus.status_code == 200
    k2 = vastaus.json()
    assert k2["tila"] == "perilla"
    assert k2["kyydissa_klo"] == k["kyydissa_klo"]   # ei ylikirjoiteta
    assert datetime.fromisoformat(k2["perilla_klo"]) >= datetime.fromisoformat(k["kyydissa_klo"])
    assert k2["kuitattu"] is True                     # perillä lukitsee reoptimoinnissa

    # Tila näkyy myös listauksessa
    keikat = (await client.get(f"/keikat?versio_id={data['v1']}", headers=tiina)).json()
    assert next(x for x in keikat if x["id"] == data["v1_tiina_1"])["tila"] == "perilla"


async def test_kuski_voi_kuitata_suoraan_perille(client, data, tiina):
    vastaus = await _aseta(client, data["v1_tiina_2"], "perilla", tiina)
    assert vastaus.status_code == 200
    assert vastaus.json()["kyydissa_klo"] is None
    assert vastaus.json()["perilla_klo"] is not None


async def test_sama_tila_uudelleen_ei_muuta_aikaleimaa(client, data, tiina):
    eka = (await _aseta(client, data["v1_tiina_1"], "kyydissa", tiina)).json()
    toka = await _aseta(client, data["v1_tiina_1"], "kyydissa", tiina)
    assert toka.status_code == 200
    assert toka.json()["kyydissa_klo"] == eka["kyydissa_klo"]


@pytest.mark.parametrize(("alku", "uusi"), [("kyydissa", "odottaa"), ("perilla", "kyydissa"), ("perilla", "odottaa")])
async def test_kuski_ei_voi_perua(client, data, tiina, alku, uusi):
    assert (await _aseta(client, data["v1_tiina_1"], alku, tiina)).status_code == 200
    vastaus = await _aseta(client, data["v1_tiina_1"], uusi, tiina)
    assert vastaus.status_code == 409
    assert "ei voi perua" in vastaus.json()["detail"]


async def test_kuski_ei_voi_kuitata_toisen_keikkaa(client, data, tiina):
    vastaus = await _aseta(client, data["v1_pekka"], "kyydissa", tiina)
    assert vastaus.status_code == 404
    # Pekan keikka ei muuttunut
    keikat = (await client.get(f"/keikat?versio_id={data['v1']}")).json()
    assert next(x for x in keikat if x["id"] == data["v1_pekka"])["tila"] == "odottaa"


async def test_kuski_ei_voi_kuitata_luonnoksen_keikkaa(client, data, tiina):
    # Luonnosversio näyttää kuskille olemattomalta (N1)
    assert (await _aseta(client, data["v2_tiina"], "kyydissa", tiina)).status_code == 404


async def test_kuski_ilman_kuskilinkkia_ei_voi_kuitata(client, data, kirjaudu):
    otsakkeet = await kirjaudu(KayttajaRooli.KUSKI)
    assert (await _aseta(client, data["v1_tiina_1"], "kyydissa", otsakkeet)).status_code == 404


async def test_kuski_ei_saa_muita_muokkauksia(client, data, tiina):
    """Poikkeus koskee vain tila-reittiä: vanha kuittaa-reitti ja muut
    muokkaukset ovat kuskilta yhä kiellettyjä."""
    vastaus = await client.patch(f"/keikat/{data['v1_tiina_1']}/kuittaa", headers=tiina)
    assert vastaus.status_code == 403
    assert vastaus.json()["detail"] == EI_OIKEUTTA_MUOKATA


async def test_tuntematon_tila_422(client, data, tiina):
    assert (await _aseta(client, data["v1_tiina_1"], "matkalla", tiina)).status_code == 422


# ---------------------------------------------------------------------------
# Koordi ja tuotanto
# ---------------------------------------------------------------------------


async def test_koordi_voi_perua_ja_aikaleimat_tyhjenevat(client, data, tiina, koordi_otsakkeet):
    await _aseta(client, data["v1_tiina_1"], "kyydissa", tiina)
    await _aseta(client, data["v1_tiina_1"], "perilla", tiina)

    vastaus = await _aseta(client, data["v1_tiina_1"], "kyydissa", koordi_otsakkeet)
    assert vastaus.status_code == 200
    k = vastaus.json()
    assert k["tila"] == "kyydissa"
    assert k["kyydissa_klo"] is not None
    assert k["perilla_klo"] is None
    assert k["kuitattu"] is False

    k = (await _aseta(client, data["v1_tiina_1"], "odottaa", koordi_otsakkeet)).json()
    assert (k["tila"], k["kyydissa_klo"], k["perilla_klo"]) == ("odottaa", None, None)


async def test_tuotanto_voi_kuitata_kenen_tahansa_keikan(client, data):
    vastaus = await _aseta(client, data["v1_pekka"], "perilla")
    assert vastaus.status_code == 200
    assert vastaus.json()["tila"] == "perilla"


async def test_luonnoksen_keikkaa_ei_voi_kuitata_409(client, data):
    vastaus = await _aseta(client, data["v2_tiina"], "kyydissa")
    assert vastaus.status_code == 409
    assert vastaus.json()["detail"] == "Vain julkaistun ajolistan keikan tilaa voi muuttaa."


async def test_olematon_keikka_404(client, data):
    assert (await _aseta(client, 99999, "kyydissa")).status_code == 404


# ---------------------------------------------------------------------------
# Uudelleenoptimointi
# ---------------------------------------------------------------------------


async def test_reoptimointi_lukitsee_kyydissa_olevan_ja_kopioi_tilan(client, db_session):
    """Iltapäivän nouto (13:40) on kyydissä jo klo 13:00, eli ennen
    suunniteltua noutoaikaa. Se ei saa siirtyä toiselle kuskille, vaikka
    kuski poistetaan pelistä."""
    paiva_id, pk_a, pk_b, versio_id = await _seed_reoptimointi(db_session)
    keikat = (await client.get(f"/keikat?versio_id={versio_id}")).json()
    ilta_id = next(k["id"] for k in keikat if k["nouto_klo"] == "13:40:00")
    kyydissa = (await _aseta(client, ilta_id, "kyydissa")).json()

    rivi = (await client.get(f"/paiva-kuskit/{pk_a}")).json()
    rivi.pop("id")
    rivi["tarjolla"] = False
    assert (await client.put(f"/paiva-kuskit/{pk_a}", json=rivi)).status_code == 200

    tulos = await _reoptimoi(client, paiva_id, versio_id, nyt="13:00")
    kuski_id, ilta = _keikka(tulos, "Iltapäivän nouto")
    assert kuski_id == pk_a
    assert ilta["lukittu"] is True
    assert ilta["tila"] == "kyydissa"

    uudet = (await client.get(f"/keikat?versio_id={tulos['versio_id']}")).json()
    uusi = next(k for k in uudet if k["tehtava_id"] == ilta["tehtava_id"])
    assert uusi["tila"] == "kyydissa"
    assert uusi["kyydissa_klo"] == kyydissa["kyydissa_klo"]


async def test_reoptimointi_ei_lukitse_odottavaa(client, db_session):
    paiva_id, pk_a, pk_b, versio_id = await _seed_reoptimointi(db_session)
    # Varmistus: siemen ei aseta tilaa
    await db_session.execute(update(Keikka).values(tila=KeikkaTila.ODOTTAA))
    await db_session.commit()

    tulos = await _reoptimoi(client, paiva_id, versio_id, nyt="07:00")
    _, ilta = _keikka(tulos, "Iltapäivän nouto")
    assert ilta["lukittu"] is False
    assert ilta["tila"] == "odottaa"

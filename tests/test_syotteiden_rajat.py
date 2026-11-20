"""L3: syötteiden rajat. Liian pitkät merkkijonot, negatiiviset määrät,
hinnat ja bufferit sekä liian pitkä optimoinnin aikaraja → 422.

Jokaiselle resurssille tarkistetaan ensin, että perussyöte menee läpi
(201), jotta 422 johtuu varmasti testattavasta kentästä eikä muusta
virheestä.
"""

import pytest

from app.schemas import (
    NIMI_MAX,
    OPTIMOINTI_AIKARAJA_MAX_S,
    OSOITE_MAX,
    PUHELIN_MAX,
    TEKSTI_MAX,
)

PITKA = "x" * 10_000


def _perus(tuotanto_id: int) -> dict[str, tuple[str, dict]]:
    return {
        "henkilo": ("/henkilot", {"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Testi"}),
        "kuski": ("/kuskit", {"tuotanto_id": tuotanto_id, "nimi": "Kuski", "sopimus": "tunti"}),
        "ajoneuvo": ("/ajoneuvot", {"tuotanto_id": tuotanto_id, "nimi": "Auto"}),
        "lokaatio": ("/lokaatiot", {"tuotanto_id": tuotanto_id, "nimi": "LOC 1"}),
        "kuvauspaiva": (
            "/kuvauspaivat",
            {"tuotanto_id": tuotanto_id, "pvm": "2026-07-10", "call_time": "07:00"},
        ),
    }


async def _paiva(client, tuotanto_id: int) -> int:
    vastaus = await client.post(
        "/kuvauspaivat",
        json={"tuotanto_id": tuotanto_id, "pvm": "2026-08-01", "call_time": "07:00"},
    )
    assert vastaus.status_code == 201
    return vastaus.json()["id"]


# (resurssi, kenttä, arvo) – kaikkien pitää antaa 422.
VIRHEELLISET = [
    ("henkilo", "nimi", "x" * (NIMI_MAX + 1)),
    ("henkilo", "roolinimi", PITKA),
    ("henkilo", "titteli", PITKA),
    ("henkilo", "puhelin", "0" * (PUHELIN_MAX + 1)),
    ("henkilo", "osoite", "x" * (OSOITE_MAX + 1)),
    ("henkilo", "huomiot", "x" * (TEKSTI_MAX + 1)),
    ("henkilo", "nouto_bufferi_min", -1),
    ("henkilo", "nouto_bufferi_min", 10_000),
    ("henkilo", "lat", 91),
    ("henkilo", "lon", -181),
    ("kuski", "nimi", PITKA),
    ("kuski", "puhelin", PITKA),
    ("kuski", "koti_osoite", PITKA),
    ("kuski", "tuntihinta_eur", -1),
    ("kuski", "tuntihinta_eur", 1_000_000),
    ("kuski", "pickup_bufferi_min", -5),
    ("kuski", "koti_lat", -91),
    ("ajoneuvo", "nimi", PITKA),
    ("ajoneuvo", "rekisteri", PITKA),
    ("ajoneuvo", "osasto", PITKA),
    ("ajoneuvo", "huomiot", PITKA),
    ("ajoneuvo", "mukavuuspaikat", 0),
    ("ajoneuvo", "mukavuuspaikat", -3),
    ("ajoneuvo", "max_paikat", 1000),
    ("lokaatio", "nimi", PITKA),
    ("lokaatio", "osoite", PITKA),
    ("lokaatio", "ajo_ohjeet", PITKA),
    ("lokaatio", "lon", 200),
    ("kuvauspaiva", "paiva_nro", PITKA),
    ("kuvauspaiva", "huomiot", PITKA),
]


@pytest.mark.parametrize(("resurssi", "kentta", "arvo"), VIRHEELLISET)
async def test_virheellinen_kentta_422(client, tuotanto_id, resurssi, kentta, arvo):
    polku, perus = _perus(tuotanto_id)[resurssi]

    ok = await client.post(polku, json=perus)
    assert ok.status_code == 201, ok.text

    vastaus = await client.post(polku, json={**perus, kentta: arvo})
    assert vastaus.status_code == 422, vastaus.text
    assert any(kentta in virhe["loc"] for virhe in vastaus.json()["detail"])


async def test_rajat_koskevat_myos_paivitysta(client, tuotanto_id):
    polku, perus = _perus(tuotanto_id)["kuski"]
    kuski = (await client.post(polku, json=perus)).json()

    vastaus = await client.put(f"/kuskit/{kuski['id']}", json={**perus, "nimi": PITKA})
    assert vastaus.status_code == 422

    vastaus = await client.put(f"/tuotannot/{tuotanto_id}", json={"nimi": "T", "tuntihinta_eur": -10})
    assert vastaus.status_code == 422


async def test_rajan_sisalla_menee_lapi(client, tuotanto_id):
    polku, perus = _perus(tuotanto_id)["henkilo"]
    vastaus = await client.post(
        polku,
        json={
            **perus,
            "nimi": "x" * NIMI_MAX,
            "huomiot": "x" * TEKSTI_MAX,
            "nouto_bufferi_min": 0,
            "lat": -90,
            "lon": 180,
        },
    )
    assert vastaus.status_code == 201, vastaus.text


@pytest.mark.parametrize(
    ("kentta", "arvo"),
    [
        ("nimi", PITKA),
        ("mista_osoite", PITKA),
        ("mihin_osoite", PITKA),
        ("huomiot", PITKA),
        ("henkiloita", -1),
        ("henkiloita", 1000),
        ("mista_lat", 100),
    ],
)
async def test_tehtavan_rajat(client, tuotanto_id, kentta, arvo):
    paiva_id = await _paiva(client, tuotanto_id)
    perus = {
        "paiva_id": paiva_id,
        "tyyppi": "tavara",
        "nimi": "Rekvisiitta",
        "henkiloita": 0,
        "mista_osoite": "Varasto",
        "mihin_osoite": "LOC 1",
    }
    ok = await client.post("/tehtavat", json=perus)
    assert ok.status_code == 201, ok.text

    vastaus = await client.post("/tehtavat", json={**perus, kentta: arvo})
    assert vastaus.status_code == 422, vastaus.text


@pytest.mark.parametrize(
    "pyynto",
    [
        {"aikaraja_s": OPTIMOINTI_AIKARAJA_MAX_S + 1},
        {"aikaraja_s": 3600},
        {"aikaraja_s": 0},
        {"aikaraja_s": -1},
        {"max_etuajassa_min": -1},
        {"max_kyytiaika_lisa_min": -1},
        {"max_kyytiaika_lisa_min": 100_000},
        {"nyt": "25:00"},
        {"nyt": PITKA},
    ],
)
async def test_optimointipyynnon_rajat(client, tuotanto_id, pyynto):
    paiva_id = await _paiva(client, tuotanto_id)
    vastaus = await client.post(f"/paivat/{paiva_id}/optimoi", json=pyynto)
    assert vastaus.status_code == 422, vastaus.text


async def test_paiva_lokaation_jarjestys_ei_negatiivinen(client, tuotanto_id):
    paiva_id = await _paiva(client, tuotanto_id)
    lokaatio = (await client.post("/lokaatiot", json={"tuotanto_id": tuotanto_id, "nimi": "L"})).json()
    vastaus = await client.post(
        "/paiva-lokaatiot",
        json={"paiva_id": paiva_id, "lokaatio_id": lokaatio["id"], "jarjestys": -1},
    )
    assert vastaus.status_code == 422


async def test_geokoodauksen_raja(client, tuotanto_id):
    for raja in (0, 1000):
        vastaus = await client.post(f"/tuotannot/{tuotanto_id}/geokoodaa?raja={raja}")
        assert vastaus.status_code == 422

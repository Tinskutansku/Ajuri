"""Savutesti päiväkohtaiselle CRUD:lle: luo tuotanto ja kuvauspäivä,
lisää paiva_kuski/paiva_henkilo/tehtava, hae listat ja päivitä/poista rivi."""


async def test_kuvauspaiva_ja_paivakohtaiset_rivit(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/kuvauspaivat",
        json={"tuotanto_id": tuotanto_id, "pvm": "2026-07-10", "call_time": "08:45:00"},
    )
    assert vastaus.status_code == 201
    paiva = vastaus.json()
    assert paiva["pvm"] == "2026-07-10"

    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Näyttelijä 1"},
    )
    henkilo_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/kuskit",
        json={"tuotanto_id": tuotanto_id, "nimi": "Kuski 1", "sopimus": "kuukausi"},
    )
    kuski_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/ajoneuvot", json={"tuotanto_id": tuotanto_id, "nimi": "Farmari 1"}
    )
    ajoneuvo_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/lokaatiot", json={"tuotanto_id": tuotanto_id, "nimi": "LOC1"}
    )
    lokaatio_id = vastaus.json()["id"]

    vastaus = await client.post(
        "/paiva-lokaatiot",
        json={"paiva_id": paiva["id"], "lokaatio_id": lokaatio_id, "jarjestys": 1},
    )
    assert vastaus.status_code == 201

    vastaus = await client.post(
        "/paiva-henkilot", json={"paiva_id": paiva["id"], "henkilo_id": henkilo_id}
    )
    assert vastaus.status_code == 201

    vastaus = await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )
    assert vastaus.status_code == 201
    paiva_kuski_id = vastaus.json()["id"]
    assert vastaus.json()["tarjolla"] is True

    vastaus = await client.post(
        "/tehtavat",
        json={
            "paiva_id": paiva["id"],
            "tyyppi": "henkilo",
            "nimi": "Nouto Näyttelijä 1",
            "henkilo_id": henkilo_id,
            "mista_osoite": "Hotelli A",
            "mihin_osoite": "LOC1",
        },
    )
    assert vastaus.status_code == 201
    tehtava_id = vastaus.json()["id"]

    vastaus = await client.get("/tehtavat", params={"paiva_id": paiva["id"]})
    assert vastaus.status_code == 200
    assert len(vastaus.json()) == 1

    vastaus = await client.put(
        f"/paiva-kuskit/{paiva_kuski_id}",
        json={"paiva_id": paiva["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id, "tarjolla": False},
    )
    assert vastaus.status_code == 200
    assert vastaus.json()["tarjolla"] is False

    vastaus = await client.delete(f"/tehtavat/{tehtava_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/tehtavat/{tehtava_id}")
    assert vastaus.status_code == 404

    # Soft delete (vaihe B2): rivi löytyy yhä sisalla_passiiviset=true:lla
    vastaus = await client.get(f"/tehtavat/{tehtava_id}", params={"sisalla_passiiviset": True})
    assert vastaus.status_code == 200
    assert vastaus.json()["aktiivinen"] is False

    vastaus = await client.get("/tehtavat", params={"paiva_id": paiva["id"]})
    assert vastaus.status_code == 200
    assert vastaus.json() == []

    vastaus = await client.get(
        "/tehtavat", params={"paiva_id": paiva["id"], "sisalla_passiiviset": True}
    )
    assert vastaus.status_code == 200
    assert len(vastaus.json()) == 1
    assert vastaus.json()[0]["id"] == tehtava_id


async def test_kuvauspaiva_404(client):
    vastaus = await client.get("/kuvauspaivat/999")
    assert vastaus.status_code == 404


async def test_henkilo_max_etuajassa_min_validoidaan(client):
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    tuotanto_id = vastaus.json()["id"]

    perus = {"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Näyttelijä 1"}

    vastaus = await client.post("/henkilot", json={**perus, "max_etuajassa_min": -1})
    assert vastaus.status_code == 422

    vastaus = await client.post("/henkilot", json={**perus, "max_etuajassa_min": 300})
    assert vastaus.status_code == 422

    vastaus = await client.post("/henkilot", json={**perus, "max_etuajassa_min": 60})
    assert vastaus.status_code == 201
    assert vastaus.json()["max_etuajassa_min"] == 60


async def test_kuvauspaiva_sama_pvm_409(client):
    """Sama päivämäärä kahdesti samaan tuotantoon -> 409 eikä 500,
    sekä luonnissa että päivityksessä. Eri tuotannossa sama pvm käy."""
    t1 = (await client.post("/tuotannot", json={"nimi": "T1"})).json()["id"]
    t2 = (await client.post("/tuotannot", json={"nimi": "T2"})).json()["id"]
    perus = {"call_time": "08:00:00"}

    eka = await client.post("/kuvauspaivat", json={**perus, "tuotanto_id": t1, "pvm": "2026-07-10"})
    assert eka.status_code == 201

    tupla = await client.post("/kuvauspaivat", json={**perus, "tuotanto_id": t1, "pvm": "2026-07-10"})
    assert tupla.status_code == 409
    assert "päivämäärälle" in tupla.json()["detail"]

    toinen_tuotanto = await client.post(
        "/kuvauspaivat", json={**perus, "tuotanto_id": t2, "pvm": "2026-07-10"}
    )
    assert toinen_tuotanto.status_code == 201

    toka = await client.post("/kuvauspaivat", json={**perus, "tuotanto_id": t1, "pvm": "2026-07-11"})
    vastaus = await client.put(
        f"/kuvauspaivat/{toka.json()['id']}",
        json={**perus, "tuotanto_id": t1, "pvm": "2026-07-10"},
    )
    assert vastaus.status_code == 409

    # Epäonnistunut päivitys ei saa jättää riviä muutettuun tilaan.
    haettu = await client.get(f"/kuvauspaivat/{toka.json()['id']}")
    assert haettu.json()["pvm"] == "2026-07-11"

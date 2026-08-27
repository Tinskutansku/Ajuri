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


async def test_kuvauspaiva_404(client):
    vastaus = await client.get("/kuvauspaivat/999")
    assert vastaus.status_code == 404

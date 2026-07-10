"""Savutesti: luo tuotanto, lisää henkilö, hae lista."""


async def test_luo_tuotanto_ja_henkilo(client):
    vastaus = await client.post(
        "/tuotannot", json={"nimi": "Testituotanto", "tuntihinta_eur": 20.0}
    )
    assert vastaus.status_code == 201
    tuotanto = vastaus.json()
    assert tuotanto["nimi"] == "Testituotanto"

    vastaus = await client.post(
        "/henkilot",
        json={
            "tuotanto_id": tuotanto["id"],
            "tyyppi": "cast",
            "nimi": "Testi Henkilö",
        },
    )
    assert vastaus.status_code == 201
    henkilo = vastaus.json()
    assert henkilo["nimi"] == "Testi Henkilö"

    vastaus = await client.get("/henkilot", params={"tuotanto_id": tuotanto["id"]})
    assert vastaus.status_code == 200
    henkilot = vastaus.json()
    assert len(henkilot) == 1
    assert henkilot[0]["id"] == henkilo["id"]

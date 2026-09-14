"""Vaihe F: henkilo/kuski/lokaatio soft delete, sisalla_passiiviset-suodatus,
/kaytto-endpoint ja passiivisen rivin liittämisen esto paiva_henkilo/
paiva_kuski/paiva_lokaatio-routereissa (docs/tuotekartta.md, vaihe F)."""


async def _luo_tuotanto(client) -> int:
    vastaus = await client.post("/tuotannot", json={"nimi": "Testituotanto"})
    return vastaus.json()["id"]


async def _luo_paiva(client, tuotanto_id: int, *, pvm: str, paiva_nro: str) -> dict:
    vastaus = await client.post(
        "/kuvauspaivat",
        json={
            "tuotanto_id": tuotanto_id,
            "pvm": pvm,
            "paiva_nro": paiva_nro,
            "call_time": "08:00:00",
        },
    )
    return vastaus.json()


async def _luo_henkilo(client, tuotanto_id: int, nimi: str = "Näyttelijä X") -> int:
    vastaus = await client.post(
        "/henkilot", json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": nimi}
    )
    return vastaus.json()["id"]


async def _luo_kuski(client, tuotanto_id: int, nimi: str = "Kuski X") -> int:
    vastaus = await client.post(
        "/kuskit", json={"tuotanto_id": tuotanto_id, "nimi": nimi, "sopimus": "kuukausi"}
    )
    return vastaus.json()["id"]


async def _luo_lokaatio(client, tuotanto_id: int, nimi: str = "Lokaatio X") -> int:
    vastaus = await client.post("/lokaatiot", json={"tuotanto_id": tuotanto_id, "nimi": nimi})
    return vastaus.json()["id"]


async def _luo_ajoneuvo(client, tuotanto_id: int, nimi: str = "Auto X") -> int:
    vastaus = await client.post("/ajoneuvot", json={"tuotanto_id": tuotanto_id, "nimi": nimi})
    return vastaus.json()["id"]


# ---------------------------------------------------------------------------
# Soft delete: DELETE merkitsee passiiviseksi, ei poista riviä
# ---------------------------------------------------------------------------


async def test_henkilo_soft_delete(client):
    tuotanto_id = await _luo_tuotanto(client)
    henkilo_id = await _luo_henkilo(client, tuotanto_id)

    vastaus = await client.delete(f"/henkilot/{henkilo_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/henkilot/{henkilo_id}")
    assert vastaus.status_code == 404

    vastaus = await client.get(f"/henkilot/{henkilo_id}", params={"sisalla_passiiviset": True})
    assert vastaus.status_code == 200
    assert vastaus.json()["aktiivinen"] is False

    vastaus = await client.get("/henkilot", params={"tuotanto_id": tuotanto_id})
    assert vastaus.json() == []

    vastaus = await client.get(
        "/henkilot", params={"tuotanto_id": tuotanto_id, "sisalla_passiiviset": True}
    )
    assert len(vastaus.json()) == 1
    assert vastaus.json()[0]["id"] == henkilo_id


async def test_kuski_soft_delete(client):
    tuotanto_id = await _luo_tuotanto(client)
    kuski_id = await _luo_kuski(client, tuotanto_id)

    vastaus = await client.delete(f"/kuskit/{kuski_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/kuskit/{kuski_id}")
    assert vastaus.status_code == 404

    vastaus = await client.get(f"/kuskit/{kuski_id}", params={"sisalla_passiiviset": True})
    assert vastaus.status_code == 200
    assert vastaus.json()["aktiivinen"] is False

    vastaus = await client.get("/kuskit", params={"tuotanto_id": tuotanto_id})
    assert vastaus.json() == []

    vastaus = await client.get(
        "/kuskit", params={"tuotanto_id": tuotanto_id, "sisalla_passiiviset": True}
    )
    assert len(vastaus.json()) == 1
    assert vastaus.json()[0]["id"] == kuski_id


async def test_lokaatio_soft_delete(client):
    tuotanto_id = await _luo_tuotanto(client)
    lokaatio_id = await _luo_lokaatio(client, tuotanto_id)

    vastaus = await client.delete(f"/lokaatiot/{lokaatio_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/lokaatiot/{lokaatio_id}")
    assert vastaus.status_code == 404

    vastaus = await client.get(f"/lokaatiot/{lokaatio_id}", params={"sisalla_passiiviset": True})
    assert vastaus.status_code == 200
    assert vastaus.json()["aktiivinen"] is False

    vastaus = await client.get("/lokaatiot", params={"tuotanto_id": tuotanto_id})
    assert vastaus.json() == []

    vastaus = await client.get(
        "/lokaatiot", params={"tuotanto_id": tuotanto_id, "sisalla_passiiviset": True}
    )
    assert len(vastaus.json()) == 1
    assert vastaus.json()[0]["id"] == lokaatio_id


# ---------------------------------------------------------------------------
# Regressio: alkuperäinen bugi oli DELETE -> 500 IntegrityError kun rivi on
# vielä käytössä paiva_henkilo/paiva_kuski/paiva_lokaatio-rivin kautta.
# ---------------------------------------------------------------------------


async def test_kuski_poisto_ei_kaadu_kun_paiva_kuski_viittaa_siihen(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    kuski_id = await _luo_kuski(client, tuotanto_id)
    ajoneuvo_id = await _luo_ajoneuvo(client, tuotanto_id)
    vastaus = await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )
    assert vastaus.status_code == 201
    paiva_kuski_id = vastaus.json()["id"]

    vastaus = await client.delete(f"/kuskit/{kuski_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/paiva-kuskit/{paiva_kuski_id}")
    assert vastaus.status_code == 200
    assert vastaus.json()["kuski_id"] == kuski_id


async def test_henkilo_poisto_ei_kaadu_kun_paiva_henkilo_viittaa_siihen(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    henkilo_id = await _luo_henkilo(client, tuotanto_id)
    vastaus = await client.post(
        "/paiva-henkilot", json={"paiva_id": paiva["id"], "henkilo_id": henkilo_id}
    )
    assert vastaus.status_code == 201
    rivi_id = vastaus.json()["id"]

    vastaus = await client.delete(f"/henkilot/{henkilo_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/paiva-henkilot/{rivi_id}")
    assert vastaus.status_code == 200
    assert vastaus.json()["henkilo_id"] == henkilo_id


async def test_lokaatio_poisto_ei_kaadu_kun_paiva_lokaatio_viittaa_siihen(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    lokaatio_id = await _luo_lokaatio(client, tuotanto_id)
    vastaus = await client.post(
        "/paiva-lokaatiot",
        json={"paiva_id": paiva["id"], "lokaatio_id": lokaatio_id, "jarjestys": 1},
    )
    assert vastaus.status_code == 201
    rivi_id = vastaus.json()["id"]

    vastaus = await client.delete(f"/lokaatiot/{lokaatio_id}")
    assert vastaus.status_code == 204

    vastaus = await client.get(f"/paiva-lokaatiot/{rivi_id}")
    assert vastaus.status_code == 200
    assert vastaus.json()["lokaatio_id"] == lokaatio_id


# ---------------------------------------------------------------------------
# GET /{resurssi}/{id}/kaytto
# ---------------------------------------------------------------------------


async def test_kuski_kaytto_palauttaa_kuvauspaivat_pvm_jarjestyksessa(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva1 = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    paiva2 = await _luo_paiva(client, tuotanto_id, pvm="2026-07-11", paiva_nro="23/49")
    kuski_id = await _luo_kuski(client, tuotanto_id)
    ajoneuvo_id = await _luo_ajoneuvo(client, tuotanto_id)

    vastaus = await client.get(f"/kuskit/{kuski_id}/kaytto")
    assert vastaus.status_code == 200
    assert vastaus.json() == []

    await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva2["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )
    await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva1["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )

    vastaus = await client.get(f"/kuskit/{kuski_id}/kaytto")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert len(data) == 2
    assert [d["paiva_nro"] for d in data] == ["22/49", "23/49"]
    assert [d["pvm"] for d in data] == ["2026-07-10", "2026-07-11"]
    assert data[0]["paiva_id"] == paiva1["id"]


async def test_henkilo_kaytto_tyhja_kun_ei_viittauksia(client):
    tuotanto_id = await _luo_tuotanto(client)
    henkilo_id = await _luo_henkilo(client, tuotanto_id)

    vastaus = await client.get(f"/henkilot/{henkilo_id}/kaytto")
    assert vastaus.status_code == 200
    assert vastaus.json() == []


async def test_lokaatio_kaytto_404_jos_rivi_ei_olemassa(client):
    vastaus = await client.get("/lokaatiot/999/kaytto")
    assert vastaus.status_code == 404


# ---------------------------------------------------------------------------
# Liitostaulut estävät passiivisen perusdatarivin liittämisen
# ---------------------------------------------------------------------------


async def test_paiva_kuski_post_ei_salli_passiivista_kuskia(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    kuski_id = await _luo_kuski(client, tuotanto_id)
    ajoneuvo_id = await _luo_ajoneuvo(client, tuotanto_id)
    await client.delete(f"/kuskit/{kuski_id}")

    vastaus = await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )
    assert vastaus.status_code == 422

    # Regressio: aktiiviseen kuskiin liittäminen toimii kuten ennen.
    toinen_kuski_id = await _luo_kuski(client, tuotanto_id, nimi="Kuski Y")
    vastaus = await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva["id"], "kuski_id": toinen_kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )
    assert vastaus.status_code == 201


async def test_paiva_kuski_put_ei_salli_passiivista_kuskia(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    kuski_id = await _luo_kuski(client, tuotanto_id)
    ajoneuvo_id = await _luo_ajoneuvo(client, tuotanto_id)
    vastaus = await client.post(
        "/paiva-kuskit",
        json={"paiva_id": paiva["id"], "kuski_id": kuski_id, "ajoneuvo_id": ajoneuvo_id},
    )
    rivi_id = vastaus.json()["id"]

    await client.delete(f"/kuskit/{kuski_id}")

    vastaus = await client.put(
        f"/paiva-kuskit/{rivi_id}",
        json={
            "paiva_id": paiva["id"],
            "kuski_id": kuski_id,
            "ajoneuvo_id": ajoneuvo_id,
            "tarjolla": False,
        },
    )
    assert vastaus.status_code == 422


async def test_paiva_henkilo_post_ei_salli_passiivista_henkiloa(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    henkilo_id = await _luo_henkilo(client, tuotanto_id)
    await client.delete(f"/henkilot/{henkilo_id}")

    vastaus = await client.post(
        "/paiva-henkilot", json={"paiva_id": paiva["id"], "henkilo_id": henkilo_id}
    )
    assert vastaus.status_code == 422


async def test_paiva_lokaatio_post_ei_salli_passiivista_lokaatiota(client):
    tuotanto_id = await _luo_tuotanto(client)
    paiva = await _luo_paiva(client, tuotanto_id, pvm="2026-07-10", paiva_nro="22/49")
    lokaatio_id = await _luo_lokaatio(client, tuotanto_id)
    await client.delete(f"/lokaatiot/{lokaatio_id}")

    vastaus = await client.post(
        "/paiva-lokaatiot",
        json={"paiva_id": paiva["id"], "lokaatio_id": lokaatio_id, "jarjestys": 1},
    )
    assert vastaus.status_code == 422

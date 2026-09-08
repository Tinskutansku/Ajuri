"""Testit POST /paivat/{id}/generoi-tehtavat (docs/tuotekartta.md, vaihe B)."""

from datetime import date, time

from sqlalchemy import select

from app.models import (
    AjolistaVersio,
    Henkilo,
    HenkiloTyyppi,
    Keikka,
    Kuski,
    Kuvauspaiva,
    Lokaatio,
    PaivaHenkilo,
    PaivaKuski,
    PaivaLokaatio,
    SopimusTyyppi,
    Tehtava,
    TehtavaTyyppi,
    Tuotanto,
)


async def _seed_perusta(db_session, *, montako_lokaatiota: int = 2):
    """Tuotanto + kuvauspäivä (call 08:00, wrap 18:00) + N lokaatiota
    järjestyksessä. Palauttaa (paiva, [paiva_lokaatio, ...])."""
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(
        tuotanto_id=tuotanto.id,
        pvm=date(2026, 9, 15),
        call_time=time(8, 0),
        wrap_arvio=time(18, 0),
    )
    db_session.add(paiva)
    await db_session.flush()

    paiva_lokaatiot = []
    for i in range(1, montako_lokaatiota + 1):
        lokaatio = Lokaatio(
            tuotanto_id=tuotanto.id, nimi=f"Lokaatio {i}",
            osoite=f"Osoite {i}", lat=60.0 + i, lon=24.0 + i,
        )
        db_session.add(lokaatio)
        await db_session.flush()
        pl = PaivaLokaatio(
            paiva_id=paiva.id, lokaatio_id=lokaatio.id, jarjestys=i,
            siirtyma_klo=time(11, 0) if i > 1 else None,
        )
        db_session.add(pl)
        await db_session.flush()
        pl.lokaatio = lokaatio
        paiva_lokaatiot.append(pl)

    return paiva, paiva_lokaatiot


async def _seed_henkilo(
    db_session, tuotanto_id: int, *, oletus_yksin: bool = False, max_etuajassa_min: int | None = None,
) -> Henkilo:
    henkilo = Henkilo(
        tuotanto_id=tuotanto_id, tyyppi=HenkiloTyyppi.CAST, nimi="Näyttelijä 1",
        osoite="Hotelli", lat=60.17, lon=24.94, oletus_yksin=oletus_yksin,
        max_etuajassa_min=max_etuajassa_min,
    )
    db_session.add(henkilo)
    await db_session.flush()
    return henkilo


async def test_perustapaus_luo_nouto_siirtyma_ja_paluu(client, db_session):
    paiva, lokaatiot = await _seed_perusta(db_session, montako_lokaatiota=2)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    ph = PaivaHenkilo(
        paiva_id=paiva.id, henkilo_id=henkilo.id,
        oma_auto=False, ei_paluuta=False, siirtyy=True,
    )
    db_session.add(ph)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["varoitus"] is None
    rivit = data["tehtavat"]
    assert len(rivit) == 3
    assert all(r["generoitu"] for r in rivit)

    by_tyyppi = {r["tyyppi"]: r for r in rivit}
    assert set(by_tyyppi) == {"henkilo", "siirtyma", "paluu"}

    nouto = by_tyyppi["henkilo"]
    assert nouto["mista_osoite"] == "Hotelli"
    assert nouto["mihin_osoite"] == "Osoite 1"
    assert nouto["perilla_viimeistaan"] == "08:00:00"

    siirtyma = by_tyyppi["siirtyma"]
    assert siirtyma["mista_osoite"] == "Osoite 1"
    assert siirtyma["mihin_osoite"] == "Osoite 2"
    assert siirtyma["perilla_viimeistaan"] == "11:00:00"

    paluu = by_tyyppi["paluu"]
    assert paluu["mista_osoite"] == "Osoite 2"
    assert paluu["mihin_osoite"] == "Hotelli"
    assert paluu["nouto_aikaisintaan"] == "18:00:00"
    assert paluu["nouto_viimeistaan"] == "18:25:00"


async def test_oma_auto_ei_generoi_tehtavia(client, db_session):
    paiva, _ = await _seed_perusta(db_session)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    ph = PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=True)
    db_session.add(ph)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    assert vastaus.json()["tehtavat"] == []


async def test_ei_paluuta_ei_generoi_paluuta(client, db_session):
    paiva, _ = await _seed_perusta(db_session)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    ph = PaivaHenkilo(
        paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False,
        ei_paluuta=True, siirtyy=True,
    )
    db_session.add(ph)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    tyypit = {r["tyyppi"] for r in vastaus.json()["tehtavat"]}
    assert "paluu" not in tyypit


async def test_siirtyy_false_paluu_ensimmaisesta_lokaatiosta(client, db_session):
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=2)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    ph = PaivaHenkilo(
        paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False,
        ei_paluuta=False, siirtyy=False,
    )
    db_session.add(ph)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    rivit = vastaus.json()["tehtavat"]
    tyypit = {r["tyyppi"] for r in rivit}
    assert "siirtyma" not in tyypit

    paluu = next(r for r in rivit if r["tyyppi"] == "paluu")
    assert paluu["mista_osoite"] == "Osoite 1"


async def test_yksin_periytyy_henkilon_oletuksesta(client, db_session):
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id, oletus_yksin=True)
    ph = PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False)
    db_session.add(ph)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    rivit = vastaus.json()["tehtavat"]
    assert rivit
    assert all(r["yksin"] is True for r in rivit)


async def test_henkilon_oma_siirtyma_klo_ohittaa_lokaation_yleisen(client, db_session):
    paiva, lokaatiot = await _seed_perusta(db_session, montako_lokaatiota=2)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    ph = PaivaHenkilo(
        paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False,
        siirtyy=True, siirtyma_klo=time(13, 30),
    )
    db_session.add(ph)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    siirtyma = next(r for r in vastaus.json()["tehtavat"] if r["tyyppi"] == "siirtyma")
    assert siirtyma["perilla_viimeistaan"] == "13:30:00"


async def test_uudelleenajo_korvaa_vain_generoidut_rivit(client, db_session):
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    ph = PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False)
    db_session.add(ph)

    kasin_tehty = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.TAVARA, nimi="Käsin lisätty rekvisiitta",
        mista_osoite="A", mihin_osoite="B", generoitu=False,
    )
    db_session.add(kasin_tehty)
    await db_session.commit()
    kasin_tehty_id = kasin_tehty.id

    vastaus1 = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus1.status_code == 200
    generoituja_1 = len(vastaus1.json()["tehtavat"])
    assert generoituja_1 > 0

    vastaus2 = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus2.status_code == 200
    assert len(vastaus2.json()["tehtavat"]) == generoituja_1

    kaikki = (
        await db_session.execute(select(Tehtava).where(Tehtava.paiva_id == paiva.id))
    ).scalars().all()
    # Vanhoja generoituja rivejä ei poisteta (soft delete) - kannassa on nyt
    # sekä ensimmäisen että toisen ajon rivit, plus käsin tehty.
    assert len(kaikki) == 2 * generoituja_1 + 1
    aktiiviset = [t for t in kaikki if t.aktiivinen]
    assert len(aktiiviset) == generoituja_1 + 1
    passiiviset = [t for t in kaikki if not t.aktiivinen]
    assert len(passiiviset) == generoituja_1
    assert all(t.generoitu for t in passiiviset)

    kasin_edelleen = await db_session.get(Tehtava, kasin_tehty_id)
    assert kasin_edelleen is not None
    assert kasin_edelleen.generoitu is False
    assert kasin_edelleen.aktiivinen is True
    assert kasin_edelleen.nimi == "Käsin lisätty rekvisiitta"


async def test_404_olematon_paiva(client):
    vastaus = await client.post("/paivat/999/generoi-tehtavat")
    assert vastaus.status_code == 404


async def test_422_ei_lokaatioita(client, db_session):
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    paiva = Kuvauspaiva(
        tuotanto_id=tuotanto.id, pvm=date(2026, 9, 15), call_time=time(8, 0),
    )
    db_session.add(paiva)
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 422


async def test_422_puuttuva_wrap_arvio_kun_paluu_tarvitaan(client, db_session):
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    paiva = Kuvauspaiva(
        tuotanto_id=tuotanto.id, pvm=date(2026, 9, 15), call_time=time(8, 0),
    )
    db_session.add(paiva)
    await db_session.flush()
    lokaatio = Lokaatio(tuotanto_id=tuotanto.id, nimi="Lokaatio 1", osoite="Osoite 1")
    db_session.add(lokaatio)
    await db_session.flush()
    db_session.add(PaivaLokaatio(paiva_id=paiva.id, lokaatio_id=lokaatio.id, jarjestys=1))
    henkilo = await _seed_henkilo(db_session, tuotanto.id)
    db_session.add(PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False))
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 422


async def test_regenerointi_onnistuu_kun_vanhaan_generoituun_viittaa_keikka(client, db_session):
    """Vaihe B2: soft delete poistaa FK-ongelman kokonaan - regenerointi ei
    enää törmää 409:ään vaikka vanhaan generoituun tehtävään viittaisi jo
    optimoitu Keikka. Vanha rivi jää kantaan aktiivinen=False, Keikka/
    AjolistaVersio säilyvät ehjinä."""
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    db_session.add(
        PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False, ei_paluuta=True)
    )
    await db_session.commit()

    vastaus1 = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus1.status_code == 200
    rivit = vastaus1.json()["tehtavat"]
    assert len(rivit) == 1
    generoitu_tehtava_id = rivit[0]["id"]

    kuski = Kuski(tuotanto_id=paiva.tuotanto_id, nimi="Kuski 1", sopimus=SopimusTyyppi.KUUKAUSI)
    db_session.add(kuski)
    await db_session.flush()
    paiva_kuski = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id)
    db_session.add(paiva_kuski)
    await db_session.flush()
    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1)
    db_session.add(versio)
    await db_session.flush()
    keikka = Keikka(
        versio_id=versio.id, tehtava_id=generoitu_tehtava_id, paiva_kuski_id=paiva_kuski.id,
        nouto_klo=time(7, 0), jatto_klo=time(7, 15), jarjestys=1,
    )
    db_session.add(keikka)
    await db_session.commit()

    vastaus2 = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus2.status_code == 200
    uudet = vastaus2.json()["tehtavat"]
    assert len(uudet) == 1
    assert uudet[0]["id"] != generoitu_tehtava_id

    vanha = await db_session.get(Tehtava, generoitu_tehtava_id)
    assert vanha is not None
    assert vanha.aktiivinen is False

    keikka_edelleen = await db_session.get(Keikka, keikka.id)
    assert keikka_edelleen is not None
    assert keikka_edelleen.tehtava_id == generoitu_tehtava_id


async def test_varoitus_kun_julkaistu_versio_viittaa_vain_kasin_luotuihin(client, db_session):
    """Julkaistun version keikat viittaavat vain käsin luotuun tehtävään ->
    generointi ei törmää 409:ään (ks. edellinen keskustelu), mutta vastauksessa
    pitää olla varoitus koska julkaistu versio ei sisällä uusia tehtäviä."""
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    db_session.add(PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False))

    kasin_tehty = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.TAVARA, nimi="Käsin lisätty rekvisiitta",
        mista_osoite="A", mihin_osoite="B", generoitu=False,
    )
    db_session.add(kasin_tehty)
    await db_session.flush()

    kuski = Kuski(tuotanto_id=paiva.tuotanto_id, nimi="Kuski 1", sopimus=SopimusTyyppi.KUUKAUSI)
    db_session.add(kuski)
    await db_session.flush()
    paiva_kuski = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id)
    db_session.add(paiva_kuski)
    await db_session.flush()
    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True)
    db_session.add(versio)
    await db_session.flush()
    db_session.add(
        Keikka(
            versio_id=versio.id, tehtava_id=kasin_tehty.id, paiva_kuski_id=paiva_kuski.id,
            nouto_klo=time(7, 0), jatto_klo=time(7, 15), jarjestys=1,
        )
    )
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert data["varoitus"] is not None
    assert "optimointi" in data["varoitus"].lower()
    assert len(data["tehtavat"]) > 0


async def test_ei_varoitusta_kun_ei_julkaistua_versiota(client, db_session):
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    db_session.add(PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False))
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    assert vastaus.json()["varoitus"] is None


async def test_max_etuajassa_min_asettaa_perilla_aikaisintaan(client, db_session):
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id, max_etuajassa_min=15)
    db_session.add(PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False))
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    nouto = next(r for r in vastaus.json()["tehtavat"] if r["tyyppi"] == "henkilo")
    assert nouto["perilla_viimeistaan"] == "08:00:00"
    assert nouto["perilla_aikaisintaan"] == "07:45:00"


async def test_max_etuajassa_min_none_ei_aseta_perilla_aikaisintaan(client, db_session):
    paiva, _ = await _seed_perusta(db_session, montako_lokaatiota=1)
    henkilo = await _seed_henkilo(db_session, paiva.tuotanto_id)
    db_session.add(PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id, oma_auto=False))
    await db_session.commit()

    vastaus = await client.post(f"/paivat/{paiva.id}/generoi-tehtavat")
    assert vastaus.status_code == 200
    nouto = next(r for r in vastaus.json()["tehtavat"] if r["tyyppi"] == "henkilo")
    assert nouto["perilla_aikaisintaan"] is None

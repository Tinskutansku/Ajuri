"""Testit POST /versiot/{id}/julkaise ja PATCH /keikat/{id}/kuittaa.
Ajolista_versio/keikka-rivit eivät ole oman CRUD:in takana (syntyvät vain
optimoinnista), joten ne seedataan suoraan ORM:lla."""

from datetime import date, time

from sqlalchemy import select

from app.models import (
    Ajoneuvo,
    AjolistaVersio,
    Keikka,
    Kuski,
    Kuvauspaiva,
    PaivaKuski,
    SopimusTyyppi,
    Tehtava,
    TehtavaTyyppi,
    Tuotanto,
)


async def _seed_kaksi_versiota(db_session) -> tuple[int, int]:
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    v1 = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True)
    v2 = AjolistaVersio(paiva_id=paiva.id, versio_nro=2, julkaistu=False)
    db_session.add_all([v1, v2])
    await db_session.commit()
    return v1.id, v2.id


async def test_julkaise_versio_poistaa_julkaisun_muilta_saman_paivan_versioilta(
    client, db_session
):
    v1_id, v2_id = await _seed_kaksi_versiota(db_session)

    vastaus = await client.post(f"/versiot/{v2_id}/julkaise")
    assert vastaus.status_code == 200
    assert vastaus.json()["julkaistu"] is True

    tulos = await db_session.execute(select(AjolistaVersio).where(AjolistaVersio.id == v1_id))
    v1_paivitetty = tulos.scalar_one()
    assert v1_paivitetty.julkaistu is False


async def test_julkaise_versio_404(client):
    vastaus = await client.post("/versiot/999/julkaise")
    assert vastaus.status_code == 404


async def _seed_paiva(db_session) -> int:
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.commit()
    return paiva.id


async def test_julkaise_versio_antaa_seuraavan_varin_jarjestyksessa(client, db_session):
    paiva_id = await _seed_paiva(db_session)
    versiot = [AjolistaVersio(paiva_id=paiva_id, versio_nro=n) for n in range(1, 7)]
    db_session.add_all(versiot)
    await db_session.commit()

    odotetut = ["WHITE", "BLUE", "PINK", "YELLOW", "2. WHITE", "2. BLUE"]
    for versio, odotettu in zip(versiot, odotetut):
        vastaus = await client.post(f"/versiot/{versio.id}/julkaise")
        assert vastaus.status_code == 200
        assert vastaus.json()["tunniste"] == odotettu

    # Aiempien versioiden tunnisteet säilyvät vaikka julkaistu vaihtuu pois
    tulos = await db_session.execute(select(AjolistaVersio).where(AjolistaVersio.paiva_id == paiva_id))
    tunnisteet = {v.versio_nro: v.tunniste for v in tulos.scalars().all()}
    assert tunnisteet == {1: "WHITE", 2: "BLUE", 3: "PINK", 4: "YELLOW", 5: "2. WHITE", 6: "2. BLUE"}


async def test_julkaise_versio_uudelleen_ei_vaihda_tunnistetta(client, db_session):
    paiva_id = await _seed_paiva(db_session)
    v1 = AjolistaVersio(paiva_id=paiva_id, versio_nro=1)
    v2 = AjolistaVersio(paiva_id=paiva_id, versio_nro=2)
    db_session.add_all([v1, v2])
    await db_session.commit()

    await client.post(f"/versiot/{v1.id}/julkaise")
    await client.post(f"/versiot/{v2.id}/julkaise")

    vastaus = await client.post(f"/versiot/{v1.id}/julkaise")
    assert vastaus.status_code == 200
    assert vastaus.json()["tunniste"] == "WHITE"


async def test_jokaisella_paivalla_oma_varikierto(client, db_session):
    paiva_a_id = await _seed_paiva(db_session)
    paiva_b_id = await _seed_paiva(db_session)

    v_a1 = AjolistaVersio(paiva_id=paiva_a_id, versio_nro=1)
    v_a2 = AjolistaVersio(paiva_id=paiva_a_id, versio_nro=2)
    v_b1 = AjolistaVersio(paiva_id=paiva_b_id, versio_nro=1)
    db_session.add_all([v_a1, v_a2, v_b1])
    await db_session.commit()

    await client.post(f"/versiot/{v_a1.id}/julkaise")
    await client.post(f"/versiot/{v_a2.id}/julkaise")

    vastaus = await client.post(f"/versiot/{v_b1.id}/julkaise")
    assert vastaus.status_code == 200
    assert vastaus.json()["tunniste"] == "WHITE"


async def _seed_keikka(db_session) -> int:
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    kuski = Kuski(tuotanto_id=tuotanto.id, nimi="Kuski 1", sopimus=SopimusTyyppi.KUUKAUSI)
    ajoneuvo = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto 1")
    db_session.add_all([kuski, ajoneuvo])
    await db_session.flush()

    paiva_kuski = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=ajoneuvo.id)
    db_session.add(paiva_kuski)
    await db_session.flush()

    tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Nouto",
        mista_osoite="A", mihin_osoite="B",
    )
    db_session.add(tehtava)
    await db_session.flush()

    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1)
    db_session.add(versio)
    await db_session.flush()

    keikka = Keikka(
        versio_id=versio.id, tehtava_id=tehtava.id, paiva_kuski_id=paiva_kuski.id,
        nouto_klo=time(7, 0), jatto_klo=time(7, 15), jarjestys=1,
    )
    db_session.add(keikka)
    await db_session.commit()
    return keikka.id


async def test_kuittaa_keikka_asettaa_kuitatun_todeksi(client, db_session):
    keikka_id = await _seed_keikka(db_session)

    vastaus = await client.patch(f"/keikat/{keikka_id}/kuittaa")
    assert vastaus.status_code == 200
    assert vastaus.json()["kuitattu"] is True

    tulos = await db_session.execute(select(Keikka).where(Keikka.id == keikka_id))
    assert tulos.scalar_one().kuitattu is True


async def test_kuittaa_keikka_404(client):
    vastaus = await client.patch("/keikat/999/kuittaa")
    assert vastaus.status_code == 404

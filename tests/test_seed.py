"""Testit demo-seedille (app/seed.py): seed + "Generoi tehtävät" ei saa
tuottaa tuplanoutoja, ja seedin uudelleenajo on idempotentti myös
generoinnin jälkeen ja vanhalle kannalle."""

from collections import Counter

from sqlalchemy import select

from app.models import Tehtava, TehtavaTyyppi
from app.seed import VANHAT_TEHTAVANIMET, seed

# Päivän henkilöt, joille kuuluu nouto ja paluu (apulaisohjaajalla oma auto).
KYYDITETTAVAT = {
    "Näyttelijä 1", "Näyttelijä 2", "Näyttelijä 3", "Näyttelijä 4",
    "Ohjaaja", "Työryhmäläinen 1", "Työryhmäläinen 2",
}
ERIKOISKEIKAT = {
    "Lounashaku",
    "Rekvisiitan haku toimistolta",
    "Kortit toimistolle",
    "Lentokenttänouto (vieraileva näyttelijä)",
    "Paluu: vieraileva näyttelijä lentokentälle",
}


async def _aktiiviset(db_session, paiva_id: int) -> list[Tehtava]:
    db_session.expire_all()
    return (
        await db_session.execute(
            select(Tehtava).where(Tehtava.paiva_id == paiva_id, Tehtava.aktiivinen.is_(True))
        )
    ).scalars().all()


def _kyydit_per_henkilo(tehtavat: list[Tehtava], tyyppi: TehtavaTyyppi) -> Counter:
    return Counter(t.henkilo_id for t in tehtavat if t.tyyppi == tyyppi and t.henkilo_id)


def _tarkista_ei_tuplia(tehtavat: list[Tehtava]) -> None:
    noudot = _kyydit_per_henkilo(tehtavat, TehtavaTyyppi.HENKILO)
    paluut = _kyydit_per_henkilo(tehtavat, TehtavaTyyppi.PALUU)
    assert len(noudot) == len(KYYDITETTAVAT)
    assert len(paluut) == len(KYYDITETTAVAT)
    assert all(maara == 1 for maara in noudot.values()), noudot
    assert all(maara == 1 for maara in paluut.values()), paluut
    nimet = [t.nimi for t in tehtavat]
    assert len(nimet) == len(set(nimet)), Counter(nimet).most_common(3)
    assert not set(nimet) & set(VANHAT_TEHTAVANIMET)
    # 7 noutoa + 7 paluuta + 5 erikoiskeikkaa
    assert len(tehtavat) == 2 * len(KYYDITETTAVAT) + len(ERIKOISKEIKAT)


async def test_seed_merkitsee_henkilokyydit_generoiduiksi(db_session):
    _, paiva = await seed(db_session)
    paiva_id = paiva.id
    tehtavat = await _aktiiviset(db_session, paiva_id)

    _tarkista_ei_tuplia(tehtavat)
    for t in tehtavat:
        if t.nimi in ERIKOISKEIKAT:
            assert t.generoitu is False, t.nimi
        else:
            assert t.generoitu is True, t.nimi
            assert t.nimi.split(": ", 1)[1] in KYYDITETTAVAT


async def test_seed_ja_generointi_ei_tuota_tuplanoutoja(client, db_session):
    _, paiva = await seed(db_session)
    paiva_id = paiva.id

    vastaus = await client.post(f"/paivat/{paiva_id}/generoi-tehtavat")
    assert vastaus.status_code == 200, vastaus.text
    generoidut = vastaus.json()["tehtavat"]
    assert len(generoidut) == 2 * len(KYYDITETTAVAT)

    tehtavat = await _aktiiviset(db_session, paiva_id)
    _tarkista_ei_tuplia(tehtavat)
    # Erikoiskeikat säilyvät käsin lisättyinä generoinnin yli.
    assert {t.nimi for t in tehtavat if not t.generoitu} == ERIKOISKEIKAT


async def test_seed_uudelleen_generoinnin_jalkeen_ei_luo_tuplia(client, db_session):
    _, paiva = await seed(db_session)
    paiva_id = paiva.id
    vastaus = await client.post(f"/paivat/{paiva_id}/generoi-tehtavat")
    assert vastaus.status_code == 200, vastaus.text

    await seed(db_session)
    _tarkista_ei_tuplia(await _aktiiviset(db_session, paiva_id))

    # ... eikä seuraava generointikaan.
    vastaus = await client.post(f"/paivat/{paiva_id}/generoi-tehtavat")
    assert vastaus.status_code == 200, vastaus.text
    _tarkista_ei_tuplia(await _aktiiviset(db_session, paiva_id))


async def test_seed_korjaa_vanhan_kannan_tuplat(client, db_session):
    """Vanha kanta: seedin aiempi versio loi henkilökyydit käsin lisättyinä
    ja generointi lisäsi samat toiseen kertaan. Uudelleenajo siivoaa."""
    _, paiva = await seed(db_session)
    paiva_id = paiva.id
    tehtavat = await _aktiiviset(db_session, paiva_id)

    # Simuloidaan vanhaa tilaa: kyydit käsin lisättyinä + vanhat yhdistelmärivit.
    for t in tehtavat:
        t.generoitu = False
    malli = next(t for t in tehtavat if t.nimi == "Nouto: Näyttelijä 1")
    for nimi in VANHAT_TEHTAVANIMET:
        db_session.add(
            Tehtava(
                paiva_id=paiva_id, nimi=nimi, tyyppi=TehtavaTyyppi.HENKILO, henkiloita=2,
                mista_osoite=malli.mista_osoite, mihin_osoite=malli.mihin_osoite,
            )
        )
    await db_session.commit()
    vastaus = await client.post(f"/paivat/{paiva_id}/generoi-tehtavat")
    assert vastaus.status_code == 200, vastaus.text
    noudot = _kyydit_per_henkilo(await _aktiiviset(db_session, paiva_id), TehtavaTyyppi.HENKILO)
    assert max(noudot.values()) == 2  # tuplat ovat olemassa ennen korjausta

    await seed(db_session)
    _tarkista_ei_tuplia(await _aktiiviset(db_session, paiva_id))

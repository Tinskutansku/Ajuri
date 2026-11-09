"""Testit GET /versiot/{a}/diff/{b} (ROADMAP J1). Versiot ja keikat
seedataan suoraan ORM:lla kuten test_versiot_ja_keikat.py:ssä."""

from datetime import date, time

from app.models import (
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


async def _seed(db_session):
    """Kaksi versiota samalle päivälle:

    tehtävä           v1 (Tiina)          v2
    Näyttelijä 1      Tiina 7:00-7:20     Tiina 7:00-7:20   -> ennallaan
    Näyttelijä 2      Tiina 7:40-8:00     Tiina 8:10-8:30   -> siirtynyt
    Näyttelijä 3      Tiina 9:00-9:20     Pekka 9:00-9:20   -> kuskia vaihtanut
    Lounashaku        Tiina 11:00-11:30   -                 -> poistunut
    Lentokenttä       -                   Pekka 15:25-16:10 -> uusi
    """
    tuotanto = Tuotanto(nimi="Testituotanto")
    db_session.add(tuotanto)
    await db_session.flush()
    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    tiina = Kuski(tuotanto_id=tuotanto.id, nimi="Tiina", sopimus=SopimusTyyppi.KUUKAUSI)
    pekka = Kuski(tuotanto_id=tuotanto.id, nimi="Pekka", sopimus=SopimusTyyppi.TUNTI)
    db_session.add_all([tiina, pekka])
    await db_session.flush()
    pk_tiina = PaivaKuski(paiva_id=paiva.id, kuski_id=tiina.id)
    pk_pekka = PaivaKuski(paiva_id=paiva.id, kuski_id=pekka.id)
    db_session.add_all([pk_tiina, pk_pekka])
    await db_session.flush()

    nimet = ["Näyttelijä 1", "Näyttelijä 2", "Näyttelijä 3", "Lounashaku", "Lentokenttä"]
    t = {}
    for nimi in nimet:
        t[nimi] = Tehtava(
            paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi=nimi,
            mista_osoite="A", mihin_osoite="B",
        )
    db_session.add_all(t.values())
    await db_session.flush()

    v1 = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, kokonaiskustannus_eur=500.0)
    v2 = AjolistaVersio(paiva_id=paiva.id, versio_nro=2, kokonaiskustannus_eur=620.5)
    db_session.add_all([v1, v2])
    await db_session.flush()

    def keikka(versio, nimi, pk, alku, loppu, nro):
        return Keikka(
            versio_id=versio.id, tehtava_id=t[nimi].id, paiva_kuski_id=pk.id,
            nouto_klo=alku, jatto_klo=loppu, jarjestys=nro,
        )

    db_session.add_all([
        keikka(v1, "Näyttelijä 1", pk_tiina, time(7, 0), time(7, 20), 1),
        keikka(v1, "Näyttelijä 2", pk_tiina, time(7, 40), time(8, 0), 2),
        keikka(v1, "Näyttelijä 3", pk_tiina, time(9, 0), time(9, 20), 3),
        keikka(v1, "Lounashaku", pk_tiina, time(11, 0), time(11, 30), 4),
        keikka(v2, "Näyttelijä 1", pk_tiina, time(7, 0), time(7, 20), 1),
        keikka(v2, "Näyttelijä 2", pk_tiina, time(8, 10), time(8, 30), 2),
        keikka(v2, "Näyttelijä 3", pk_pekka, time(9, 0), time(9, 20), 1),
        keikka(v2, "Lentokenttä", pk_pekka, time(15, 25), time(16, 10), 2),
    ])
    await db_session.commit()
    return {"v1": v1.id, "v2": v2.id, "paiva": paiva.id, "tuotanto": tuotanto.id,
            "tiina": tiina.id, "pekka": pekka.id}


async def test_diff_siirtyneet_ajat(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()

    assert [d["tehtava_nimi"] for d in data["siirtyneet"]] == ["Näyttelijä 2"]
    siirtynyt = data["siirtyneet"][0]
    assert siirtynyt["nouto_klo_a"] == "07:40:00"
    assert siirtynyt["nouto_klo_b"] == "08:10:00"
    assert siirtynyt["jatto_klo_a"] == "08:00:00"
    assert siirtynyt["jatto_klo_b"] == "08:30:00"
    assert siirtynyt["kuski_nimi_a"] == siirtynyt["kuski_nimi_b"] == "Tiina"


async def test_diff_kuskia_vaihtaneet(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()

    assert [d["tehtava_nimi"] for d in data["kuskia_vaihtaneet"]] == ["Näyttelijä 3"]
    vaihtanut = data["kuskia_vaihtaneet"][0]
    assert (vaihtanut["kuski_id_a"], vaihtanut["kuski_nimi_a"]) == (ids["tiina"], "Tiina")
    assert (vaihtanut["kuski_id_b"], vaihtanut["kuski_nimi_b"]) == (ids["pekka"], "Pekka")
    # Ajat eivät muuttuneet, joten ei näy siirtyneissä
    assert "Näyttelijä 3" not in [d["tehtava_nimi"] for d in data["siirtyneet"]]


async def test_diff_uudet(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()

    assert [d["tehtava_nimi"] for d in data["uudet"]] == ["Lentokenttä"]
    uusi = data["uudet"][0]
    assert uusi["kuski_nimi_a"] is None and uusi["nouto_klo_a"] is None
    assert uusi["kuski_nimi_b"] == "Pekka"
    assert uusi["nouto_klo_b"] == "15:25:00"


async def test_diff_poistuneet(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()

    assert [d["tehtava_nimi"] for d in data["poistuneet"]] == ["Lounashaku"]
    poistunut = data["poistuneet"][0]
    assert poistunut["kuski_nimi_a"] == "Tiina"
    assert poistunut["kuski_nimi_b"] is None and poistunut["nouto_klo_b"] is None


async def test_diff_ennallaan_ja_kuskikohtainen_muutos(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()

    assert data["ennallaan_lkm"] == 1
    assert data["kuskit"] == [
        {"kuski_id": ids["pekka"], "kuski_nimi": "Pekka", "keikkoja_a": 0, "keikkoja_b": 2, "muutos": 2},
        {"kuski_id": ids["tiina"], "kuski_nimi": "Tiina", "keikkoja_a": 4, "keikkoja_b": 2, "muutos": -2},
    ]


async def test_diff_kustannukset_tuotannolle(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()

    assert data["kokonaiskustannus_a_eur"] == 500.0
    assert data["kokonaiskustannus_b_eur"] == 620.5
    assert data["kustannusmuutos_eur"] == 120.5


async def test_diff_kuski_ei_nae_kustannusmuutoksia(client, db_session):
    ids = await _seed(db_session)
    vastaus = await client.get(
        f"/versiot/{ids['v1']}/diff/{ids['v2']}", headers={"X-Rooli": "kuski"}
    )
    assert vastaus.status_code == 200
    data = vastaus.json()
    assert "kustannusmuutos_eur" not in data
    assert "kokonaiskustannus_a_eur" not in data
    assert "kokonaiskustannus_b_eur" not in data
    assert not any("eur" in avain for avain in data)
    # Muut muutokset näkyvät kuskillekin
    assert [d["tehtava_nimi"] for d in data["siirtyneet"]] == ["Näyttelijä 2"]


async def test_diff_samaan_versioon_on_tyhja(client, db_session):
    ids = await _seed(db_session)
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v1']}")).json()

    assert data["siirtyneet"] == data["kuskia_vaihtaneet"] == []
    assert data["uudet"] == data["poistuneet"] == data["kuskit"] == []
    assert data["ennallaan_lkm"] == 4
    assert data["kustannusmuutos_eur"] == 0.0


async def test_diff_kustannusmuutos_none_jos_kustannus_puuttuu(client, db_session):
    ids = await _seed(db_session)
    v3 = AjolistaVersio(paiva_id=ids["paiva"], versio_nro=3, kokonaiskustannus_eur=None)
    db_session.add(v3)
    await db_session.commit()

    data = (await client.get(f"/versiot/{ids['v1']}/diff/{v3.id}")).json()
    assert data["kustannusmuutos_eur"] is None
    # Tyhjä versio: kaikki v1:n keikat poistuneita
    assert len(data["poistuneet"]) == 4


async def test_diff_404_jos_versio_puuttuu(client, db_session):
    ids = await _seed(db_session)
    assert (await client.get(f"/versiot/{ids['v1']}/diff/999")).status_code == 404
    assert (await client.get(f"/versiot/999/diff/{ids['v1']}")).status_code == 404


async def test_diff_400_jos_eri_paivat(client, db_session):
    ids = await _seed(db_session)
    toinen_paiva = Kuvauspaiva(tuotanto_id=ids["tuotanto"], pvm=date(2026, 7, 11), call_time=time(8, 0))
    db_session.add(toinen_paiva)
    await db_session.flush()
    vieras = AjolistaVersio(paiva_id=toinen_paiva.id, versio_nro=1)
    db_session.add(vieras)
    await db_session.commit()

    vastaus = await client.get(f"/versiot/{ids['v1']}/diff/{vieras.id}")
    assert vastaus.status_code == 400

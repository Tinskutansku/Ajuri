"""N1: KUSKI-rooli näkee vain omat keikkansa julkaistusta versiosta.

Muiden kuskien keikat, luonnosversiot ja vanhat versiot eivät näy millään
reitillä. Säännöt ovat app/omistus.py:ssä (hae_versio,
rajaa_kuskin_versiot, rajaa_kuskin_keikat). Kustannuskenttien piilotus
on testattu test_roolinakyvyys.py:ssä ja test_versiodiff.py:ssä.
"""

from datetime import date, time

from tests.apu_tuotanto import hae_testituotanto

from app.models import (
    AjolistaVersio,
    KayttajaRooli,
    Keikka,
    Kuski,
    Kuvauspaiva,
    PaivaKuski,
    SopimusTyyppi,
    Tehtava,
    TehtavaTyyppi,
)


async def _seed(db_session) -> dict:
    """Yksi päivä, kaksi kuskia (Tiina, Pekka), kaksi versiota:

    v1 julkaistu:   Tiina: Näyttelijä 1, Näyttelijä 2   Pekka: Lentokenttä
    v2 luonnos:     Tiina: Näyttelijä 1                 Pekka: Näyttelijä 2, Lentokenttä
    """
    tuotanto = await hae_testituotanto(db_session)
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

    t = {}
    for nimi in ("Näyttelijä 1", "Näyttelijä 2", "Lentokenttä"):
        t[nimi] = Tehtava(
            paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi=nimi,
            mista_osoite="A", mihin_osoite="B",
        )
    db_session.add_all(t.values())
    await db_session.flush()

    v1 = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True, kokonaiskustannus_eur=300.0)
    v2 = AjolistaVersio(paiva_id=paiva.id, versio_nro=2, julkaistu=False, kokonaiskustannus_eur=280.0)
    db_session.add_all([v1, v2])
    await db_session.flush()

    def keikka(versio, nimi, pk, alku, nro):
        return Keikka(
            versio_id=versio.id, tehtava_id=t[nimi].id, paiva_kuski_id=pk.id,
            nouto_klo=alku, jatto_klo=time(alku.hour, alku.minute + 20), jarjestys=nro,
        )

    k = {
        "v1_tiina_1": keikka(v1, "Näyttelijä 1", pk_tiina, time(7, 0), 1),
        "v1_tiina_2": keikka(v1, "Näyttelijä 2", pk_tiina, time(8, 0), 2),
        "v1_pekka": keikka(v1, "Lentokenttä", pk_pekka, time(15, 0), 1),
        "v2_tiina": keikka(v2, "Näyttelijä 1", pk_tiina, time(7, 0), 1),
        "v2_pekka_1": keikka(v2, "Näyttelijä 2", pk_pekka, time(8, 0), 1),
        "v2_pekka_2": keikka(v2, "Lentokenttä", pk_pekka, time(15, 0), 2),
    }
    db_session.add_all(k.values())
    await db_session.commit()
    return {
        "paiva": paiva.id, "v1": v1.id, "v2": v2.id, "tiina": tiina.id, "pekka": pekka.id,
        "pk_tiina": pk_tiina.id, "pk_pekka": pk_pekka.id,
        **{nimi: keikka.id for nimi, keikka in k.items()},
    }


async def _tiina(kirjaudu, ids) -> dict[str, str]:
    return await kirjaudu(KayttajaRooli.KUSKI, kuski_id=ids["tiina"])


async def test_kuski_nakee_vain_omat_keikkansa_julkaistusta_versiosta(client, db_session, kirjaudu):
    ids = await _seed(db_session)
    tiina = await _tiina(kirjaudu, ids)

    # Ilman suodatinta: vain omat, vain julkaistusta versiosta
    rivit = (await client.get("/keikat", headers=tiina)).json()
    assert sorted(r["id"] for r in rivit) == sorted([ids["v1_tiina_1"], ids["v1_tiina_2"]])
    assert all(r["paiva_kuski_id"] == ids["pk_tiina"] for r in rivit)

    # Julkaistun version suodattimella sama tulos
    vastaus = await client.get("/keikat", params={"versio_id": ids["v1"]}, headers=tiina)
    assert vastaus.status_code == 200
    assert sorted(r["id"] for r in vastaus.json()) == sorted([ids["v1_tiina_1"], ids["v1_tiina_2"]])


async def test_kuski_ei_nae_luonnosversiota_eika_sen_keikkoja(client, db_session, kirjaudu):
    ids = await _seed(db_session)
    tiina = await _tiina(kirjaudu, ids)

    vastaus = await client.get("/keikat", params={"versio_id": ids["v2"]}, headers=tiina)
    assert vastaus.status_code == 404
    vastaus = await client.get(f"/versiot/{ids['v2']}", headers=tiina)
    assert vastaus.status_code == 404
    # Sama viesti kuin olemattomalle versiolle: ei paljasteta luonnoksen olemassaoloa
    olematon = await client.get("/versiot/999999", headers=tiina)
    assert vastaus.json() == olematon.json()

    for params in ({"paiva_id": ids["paiva"]}, {}, {"julkaistu": False}):
        rivit = (await client.get("/versiot", params=params, headers=tiina)).json()
        assert [r["id"] for r in rivit] == ([] if params.get("julkaistu") is False else [ids["v1"]])


async def test_kuski_ei_saa_diffia_luonnokseen(client, db_session, kirjaudu):
    ids = await _seed(db_session)
    tiina = await _tiina(kirjaudu, ids)
    for a, b in ((ids["v1"], ids["v2"]), (ids["v2"], ids["v1"]), (ids["v2"], ids["v2"])):
        vastaus = await client.get(f"/versiot/{a}/diff/{b}", headers=tiina)
        assert vastaus.status_code == 404, (a, b)


async def test_kuskin_diff_sisaltaa_vain_omat_keikat(client, db_session, kirjaudu):
    """API:n kautta julkaistuna on kerrallaan vain yksi versio päivässä,
    mutta jos kaksi olisi julkaistuna, diff ei silti näytä muiden keikkoja."""
    ids = await _seed(db_session)
    (await db_session.get(AjolistaVersio, ids["v2"])).julkaistu = True
    await db_session.commit()
    tiina = await _tiina(kirjaudu, ids)

    vastaus = await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}", headers=tiina)
    assert vastaus.status_code == 200
    data = vastaus.json()
    # Näyttelijä 2 siirtyi Tiinalta Pekalle: Tiinalle se näkyy poistuneena
    # ilman Pekan tietoja. Pekan Lentokenttä ei näy lainkaan.
    assert [d["tehtava_nimi"] for d in data["poistuneet"]] == ["Näyttelijä 2"]
    assert data["uudet"] == data["siirtyneet"] == data["kuskia_vaihtaneet"] == []
    assert data["ennallaan_lkm"] == 1
    assert [k["kuski_id"] for k in data["kuskit"]] == [ids["tiina"]]
    assert "Pekka" not in vastaus.text
    assert "Lentokenttä" not in vastaus.text

    # Vastakoe: tuotanto näkee saman diffin kokonaan
    data = (await client.get(f"/versiot/{ids['v1']}/diff/{ids['v2']}")).json()
    assert [d["tehtava_nimi"] for d in data["kuskia_vaihtaneet"]] == ["Näyttelijä 2"]
    assert {k["kuski_id"] for k in data["kuskit"]} == {ids["tiina"], ids["pekka"]}


async def test_toinen_kuski_nakee_omansa(client, db_session, kirjaudu):
    ids = await _seed(db_session)
    pekka = await kirjaudu(KayttajaRooli.KUSKI, kuski_id=ids["pekka"])
    rivit = (await client.get("/keikat", headers=pekka)).json()
    assert [r["id"] for r in rivit] == [ids["v1_pekka"]]


async def test_kuskiin_linkittamaton_kayttaja_ei_nae_keikkoja(client, db_session, kuski_otsakkeet):
    ids = await _seed(db_session)
    assert (await client.get("/keikat", headers=kuski_otsakkeet)).json() == []
    vastaus = await client.get("/keikat", params={"versio_id": ids["v1"]}, headers=kuski_otsakkeet)
    assert vastaus.json() == []


async def test_optimoinnin_tila_kertoo_kuskille_julkaistun_version(client, db_session, kirjaudu):
    ids = await _seed(db_session)
    tiina = await _tiina(kirjaudu, ids)
    polku = f"/paivat/{ids['paiva']}/optimointi"
    assert (await client.get(polku, headers=tiina)).json()["viimeisin_versio_id"] == ids["v1"]
    assert (await client.get(polku)).json()["viimeisin_versio_id"] == ids["v2"]


async def test_tuotanto_ja_koordi_nakevat_kaikki_keikat(client, db_session, koordi_otsakkeet):
    ids = await _seed(db_session)
    kaikki = sorted(v for k, v in ids.items() if k.startswith(("v1_", "v2_")))
    for otsakkeet in ({}, koordi_otsakkeet):
        rivit = (await client.get("/keikat", headers=otsakkeet)).json()
        assert sorted(r["id"] for r in rivit) == kaikki
        vastaus = await client.get(f"/versiot/{ids['v2']}", headers=otsakkeet)
        assert vastaus.status_code == 200

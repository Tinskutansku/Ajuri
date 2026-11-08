"""ROADMAP I2: "Kuski pois pelistä" -hätänappi.

Frontendin nappi tekee kaksi olemassa olevaa kutsua peräkkäin:
1) PUT /paiva-kuskit/{id} tarjolla=false (tai takaisin true)
2) POST /paivat/{id}/optimoi nyt=<kellonaika>, pohjaversio_id=<näkyvä versio>

Nämä testit varmistavat, että ketju toimii backendissä: pelistä poistetun
kuskin kuitatut (ajetut) keikat pysyvät lukittuina hänelle, ja vain hänen
ajamattomat keikkansa siirtyvät muille. Paluu peliin toimii samalla tavalla.
"""

from datetime import date, time

from sqlalchemy import update

from app.main import app
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
from app.services.router_client import get_router_client
from tests.test_optimointi_router import FakeRouterClient


async def _seed(db_session):
    """Kaksi kuskia. Kuski A:lla pohjaversiossa kaksi keikkaa: aamun nouto
    (kuitattu, eli ajettu) ja iltapäivän nouto (ei vielä ajettu)."""
    tuotanto = Tuotanto(nimi="Testituotanto", tuntihinta_eur=20.0)
    db_session.add(tuotanto)
    await db_session.flush()

    paiva = Kuvauspaiva(tuotanto_id=tuotanto.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db_session.add(paiva)
    await db_session.flush()

    kuski_a = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski A", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.0,
    )
    kuski_b = Kuski(
        tuotanto_id=tuotanto.id, nimi="Kuski B", sopimus=SopimusTyyppi.KUUKAUSI,
        koti_lat=60.0, koti_lon=24.1,
    )
    db_session.add_all([kuski_a, kuski_b])
    await db_session.flush()

    auto_a = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto A", mukavuuspaikat=4)
    auto_b = Ajoneuvo(tuotanto_id=tuotanto.id, nimi="Auto B", mukavuuspaikat=4)
    db_session.add_all([auto_a, auto_b])
    await db_session.flush()

    pk_a = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski_a.id, ajoneuvo_id=auto_a.id, tarjolla=True)
    pk_b = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski_b.id, ajoneuvo_id=auto_b.id, tarjolla=True)
    db_session.add_all([pk_a, pk_b])
    await db_session.flush()

    aamu = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Aamun nouto",
        henkiloita=1, mista_osoite="Hotelli A", mista_lat=60.01, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(7, 0),
    )
    ilta = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Iltapäivän nouto",
        henkiloita=1, mista_osoite="Hotelli B", mista_lat=60.03, mista_lon=24.0,
        mihin_osoite="LOC1", mihin_lat=60.02, mihin_lon=24.0,
        perilla_viimeistaan=time(14, 0),
    )
    db_session.add_all([aamu, ilta])
    await db_session.flush()

    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, julkaistu=True)
    db_session.add(versio)
    await db_session.flush()
    db_session.add_all(
        [
            Keikka(
                versio_id=versio.id, tehtava_id=aamu.id, paiva_kuski_id=pk_a.id,
                nouto_klo=time(6, 30), jatto_klo=time(6, 35), jarjestys=1, kuitattu=True,
            ),
            Keikka(
                versio_id=versio.id, tehtava_id=ilta.id, paiva_kuski_id=pk_a.id,
                nouto_klo=time(13, 40), jatto_klo=time(13, 45), jarjestys=2, kuitattu=False,
            ),
        ]
    )
    await db_session.commit()
    return paiva.id, pk_a.id, pk_b.id, versio.id


async def _aseta_tarjolla(client, paiva_kuski_id: int, tarjolla: bool):
    rivi = (await client.get(f"/paiva-kuskit/{paiva_kuski_id}")).json()
    rivi.pop("id")
    rivi["tarjolla"] = tarjolla
    vastaus = await client.put(f"/paiva-kuskit/{paiva_kuski_id}", json=rivi)
    assert vastaus.status_code == 200, vastaus.text
    assert vastaus.json()["tarjolla"] is tarjolla


async def _reoptimoi(client, paiva_id: int, pohjaversio_id: int, nyt: str):
    app.dependency_overrides[get_router_client] = lambda: FakeRouterClient()
    try:
        vastaus = await client.post(
            f"/paivat/{paiva_id}/optimoi",
            json={"aikaraja_s": 3, "skenaariot": False, "nyt": nyt, "pohjaversio_id": pohjaversio_id},
        )
    finally:
        del app.dependency_overrides[get_router_client]
    assert vastaus.status_code == 200, vastaus.text
    return vastaus.json()


def _keikka(data, nimi):
    """Palauttaa (kuskin paiva_kuski_id, keikka) nimen perusteella."""
    for kuski in data["kuskit"]:
        for kk in kuski["keikat"]:
            if kk["nimi"] == nimi:
                return kuski["paiva_kuski_id"], kk
    raise AssertionError(f"Keikkaa {nimi} ei löytynyt vastauksesta")


async def test_pois_pelista_kuitattu_keikka_pysyy_lukittuna(client, db_session):
    paiva_id, pk_a, pk_b, versio_id = await _seed(db_session)

    await _aseta_tarjolla(client, pk_a, False)
    data = await _reoptimoi(client, paiva_id, versio_id, nyt="07:00")

    # Ajettu keikka pysyy Kuski A:lla sellaisenaan ja lukittuna.
    kuski_id, aamu = _keikka(data, "Aamun nouto")
    assert kuski_id == pk_a
    assert aamu["lukittu"] is True
    assert aamu["kuitattu"] is True
    assert (aamu["nouto_klo"], aamu["jatto_klo"]) == ("06:30", "06:35")

    # Ajamaton keikka siirtyy pelissä olevalle kuskille.
    kuski_id, ilta = _keikka(data, "Iltapäivän nouto")
    assert kuski_id == pk_b
    assert ilta["lukittu"] is False

    # Pelistä poistetulla kuskilla ei ole yhtään lukitsematonta keikkaa.
    kuski_a = next(k for k in data["kuskit"] if k["paiva_kuski_id"] == pk_a)
    assert all(kk["lukittu"] for kk in kuski_a["keikat"])
    assert data["sijoittamatta"] == []

    # Kuittaustieto kopioituu uuteen versioon kantaan asti, joten se säilyy
    # myös seuraavassa reoptimoinnissa.
    uudet = (await client.get(f"/keikat?versio_id={data['versio_id']}")).json()
    aamu_rivi = next(k for k in uudet if k["tehtava_id"] == aamu["tehtava_id"])
    assert aamu_rivi["kuitattu"] is True
    assert aamu_rivi["paiva_kuski_id"] == pk_a


async def test_takaisin_peliin_kuitattu_keikka_pysyy_yha_lukittuna(client, db_session):
    paiva_id, pk_a, pk_b, versio_id = await _seed(db_session)

    await _aseta_tarjolla(client, pk_a, False)
    pois = await _reoptimoi(client, paiva_id, versio_id, nyt="07:00")

    # Korvaava auto löytyi: kuski takaisin peliin ja uusi optimointi
    # edellisestä (pelistä poiston) versiosta.
    await _aseta_tarjolla(client, pk_a, True)
    takaisin = await _reoptimoi(client, paiva_id, pois["versio_id"], nyt="07:10")

    kuski_id, aamu = _keikka(takaisin, "Aamun nouto")
    assert kuski_id == pk_a
    assert aamu["lukittu"] is True
    assert aamu["kuitattu"] is True
    assert aamu["nouto_klo"] == "06:30"

    # Iltapäivän nouto on yhä sijoitettu jollekin (kumpi tahansa kelpaa:
    # stabiliteettisakko suosii B:tä, jolle se siirtyi).
    kuski_id, ilta = _keikka(takaisin, "Iltapäivän nouto")
    assert kuski_id in (pk_a, pk_b)
    assert takaisin["sijoittamatta"] == []


async def test_reoptimointi_ei_sijoita_noutoa_menneisyyteen(client, db_session):
    """Tanjan päätös PR #16: menneisyyteen ei voi sijoittaa mitään.

    Ilman korjausta kuski B:lle siirtynyt nouto ajoitettiin klo 13:25, vaikka
    reoptimointi tehtiin klo 13:45 (B:llä ei ollut lukittuja keikkoja, joten
    hänen lähtöaikaansa ei rajoitettu)."""
    paiva_id, pk_a, pk_b, versio_id = await _seed(db_session)
    # Iltapäivän nouto alkaa pohjaversiossa vasta nyt-hetken jälkeen, joten
    # se ei lukitu, mutta sen aikaikkuna sallisi aiemman noudon.
    await db_session.execute(
        update(Keikka)
        .where(Keikka.versio_id == versio_id, Keikka.nouto_klo == time(13, 40))
        .values(nouto_klo=time(13, 50), jatto_klo=time(13, 55))
    )
    await db_session.commit()

    await _aseta_tarjolla(client, pk_a, False)
    data = await _reoptimoi(client, paiva_id, versio_id, nyt="13:45")

    kuski_id, ilta = _keikka(data, "Iltapäivän nouto")
    assert kuski_id == pk_b
    assert ilta["nouto_klo"] >= "13:45"
    assert data["sijoittamatta"] == []

    # Lukittu, jo ajettu keikka säilyttää silti alkuperäiset aikansa.
    _, aamu = _keikka(data, "Aamun nouto")
    assert aamu["nouto_klo"] == "06:30"

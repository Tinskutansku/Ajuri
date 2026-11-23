"""K2: kaikki reitit vaativat kirjautumisen, KUSKI ei saa muokata mitään,
ja käyttäjä näkee vain oman tuotantonsa datan.

Reittilista luetaan OpenAPI-kuvauksesta, joten uusi reitti tulee näiden
testien piiriin automaattisesti. Jos uuden reitin kuuluu olla avoin, se
lisätään AVOIMET-listaan perusteluineen.
"""

import re
from datetime import UTC, date, datetime, time, timedelta

import jwt
import pytest

from app.auth import ALGORITMI, luo_token
from app.config import settings
from app.main import app
from app.models import (
    Ajoneuvo,
    AjolistaVersio,
    Henkilo,
    HenkiloTyyppi,
    Kayttaja,
    KayttajaRooli,
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
from app.rooli import EI_KIRJAUTUNUT, EI_OIKEUTTA_MUOKATA

# Reitit, jotka toimivat ilman tokenia. /auth/mina tarkistaa tokenin itse
# (testattu test_kirjautuminen.py:ssä), mutta kuuluu silti 401-testiin.
# /auth/demo: kirjautumissivun demonapit (M2, testattu test_demotila.py:ssä).
AVOIMET = {
    ("GET", "/"),
    ("GET", "/health"),
    ("POST", "/auth/kirjaudu"),
    ("GET", "/auth/demo"),
    ("POST", "/auth/demo"),
}


def _kaikki_reitit() -> list[tuple[str, str]]:
    reitit = []
    for polku, metodit in app.openapi()["paths"].items():
        for metodi in metodit:
            reitit.append((metodi.upper(), polku))
    return sorted(reitit)


def _tayta(polku: str) -> str:
    """Polkuparametrit -> 1 (olemassaolo ei ratkaise: 401/403 tulee ennen hakua)."""
    return re.sub(r"\{[^}]+\}", "1", polku)


SUOJATUT = [r for r in _kaikki_reitit() if r not in AVOIMET]
MUOKKAAVAT = [r for r in SUOJATUT if r[0] not in ("GET", "HEAD", "OPTIONS") and r[1] != "/auth/mina"]


def test_reittilista_kattaa_api_n():
    # Varmistus, ettei parametrisointi tyhjene huomaamatta (esim. jos
    # reitit siirtyvät pois OpenAPI-kuvauksesta).
    assert len(SUOJATUT) >= 30
    assert ("POST", "/paivat/{paiva_id}/optimoi") in MUOKKAAVAT
    assert ("GET", "/osoitteet/ehdota") in SUOJATUT


# ---------------------------------------------------------------------------
# 401: ei tokenia, vanhentunut tai väärennetty token
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("metodi", "polku"), SUOJATUT, ids=[f"{m} {p}" for m, p in SUOJATUT])
async def test_reitti_ilman_tokenia_401(anon_client, metodi, polku):
    vastaus = await anon_client.request(metodi, _tayta(polku))
    assert vastaus.status_code == 401, vastaus.text
    assert vastaus.json()["detail"] == EI_KIRJAUTUNUT
    assert vastaus.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(("metodi", "polku"), sorted(AVOIMET))
async def test_avoimet_reitit_eivat_vaadi_tokenia(anon_client, metodi, polku):
    runko = {
        "/auth/kirjaudu": {"email": "ei@ole.test", "salasana": "x"},
        "/auth/demo": {"rooli": "tuotanto"},
    }.get(polku) if metodi == "POST" else None
    vastaus = await anon_client.request(metodi, polku, json=runko)
    if polku == "/auth/kirjaudu":
        # 401 tulee väärästä tunnuksesta, ei puuttuvasta tokenista
        assert vastaus.status_code == 401
        assert vastaus.json()["detail"] != EI_KIRJAUTUNUT
    elif (metodi, polku) == ("POST", "/auth/demo"):
        # Demotila on oletuksena pois: 404, ei 401
        assert vastaus.status_code == 404
    else:
        assert vastaus.status_code == 200


async def test_dokumentaatio_on_avoin_kehityksessa(anon_client):
    assert (await anon_client.get("/docs")).status_code == 200
    assert (await anon_client.get("/openapi.json")).status_code == 200


def _token(payload_muutos: dict, *, salaisuus: str | None = None) -> str:
    nyt = datetime.now(UTC)
    payload = {
        "sub": "1", "rooli": "tuotanto", "tuotanto_id": 1,
        "iat": nyt, "exp": nyt + timedelta(hours=1),
    } | payload_muutos
    return jwt.encode(payload, salaisuus or settings.jwt_secret, algorithm=ALGORITMI)


@pytest.mark.parametrize(
    "otsake",
    [
        "Bearer ei-ole-token",
        "Basic dGFuamE6c2FsYXNhbmE=",
        "Bearer " + _token({"exp": datetime.now(UTC) - timedelta(minutes=1)}),
        "Bearer " + _token({}, salaisuus="vaara-salaisuus-0123456789abcdef0123456789"),
    ],
    ids=["roskaa", "basic-auth", "vanhentunut", "vaara-allekirjoitus"],
)
async def test_kelvoton_token_401(client, otsake):
    vastaus = await client.get("/henkilot", headers={"Authorization": otsake})
    assert vastaus.status_code == 401


async def test_passivoitu_kayttaja_ja_vanhentunut_rooli_401(client, db_session, kirjaudu):
    otsakkeet = await kirjaudu(KayttajaRooli.KOORDI)
    assert (await client.get("/henkilot", headers=otsakkeet)).status_code == 200

    kayttaja = (await db_session.execute(
        Kayttaja.__table__.select().where(Kayttaja.rooli == KayttajaRooli.KOORDI)
    )).first()
    k = await db_session.get(Kayttaja, kayttaja.id)

    # Rooli vaihdettu kannassa tokenin myöntämisen jälkeen -> vanha token ei kelpaa
    k.rooli = KayttajaRooli.KUSKI
    await db_session.commit()
    assert (await client.get("/henkilot", headers=otsakkeet)).status_code == 401

    # Passivoitu käyttäjä ei pääse sisään tuoreellakaan tokenilla
    k.aktiivinen = False
    await db_session.commit()
    uusi = {"Authorization": f"Bearer {luo_token(k)}"}
    assert (await client.get("/henkilot", headers=uusi)).status_code == 401


# ---------------------------------------------------------------------------
# 403: KUSKI ei saa muokata mitään
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("metodi", "polku"), MUOKKAAVAT, ids=[f"{m} {p}" for m, p in MUOKKAAVAT])
async def test_kuski_ei_saa_muokata_403(client, kuski_otsakkeet, metodi, polku):
    vastaus = await client.request(metodi, _tayta(polku), headers=kuski_otsakkeet, json={})
    assert vastaus.status_code == 403, vastaus.text
    assert vastaus.json()["detail"] == EI_OIKEUTTA_MUOKATA


async def test_kuski_saa_lukea_ja_koordi_muokata(client, kuski_otsakkeet, koordi_otsakkeet, tuotanto_id):
    vastaus = await client.post(
        "/henkilot",
        json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "N1"},
        headers=koordi_otsakkeet,
    )
    assert vastaus.status_code == 201
    henkilo_id = vastaus.json()["id"]

    assert (await client.get(f"/henkilot/{henkilo_id}", headers=kuski_otsakkeet)).status_code == 200
    vastaus = await client.get("/henkilot", headers=kuski_otsakkeet)
    assert [h["id"] for h in vastaus.json()] == [henkilo_id]

    # Estetty muokkaus ei muuttanut mitään
    await client.delete(f"/henkilot/{henkilo_id}", headers=kuski_otsakkeet)
    assert (await client.get(f"/henkilot/{henkilo_id}")).status_code == 200


# ---------------------------------------------------------------------------
# 404: toisen tuotannon data
# ---------------------------------------------------------------------------


async def _seed_toinen_tuotanto(db) -> dict[str, int]:
    """Täysi dataketju tuotannolle, johon testikäyttäjä EI kuulu."""
    t = Tuotanto(nimi="Toinen tuotanto")
    db.add(t)
    await db.flush()
    henkilo = Henkilo(tuotanto_id=t.id, tyyppi=HenkiloTyyppi.CAST, nimi="Vieras näyttelijä")
    kuski = Kuski(tuotanto_id=t.id, nimi="Vieras kuski", sopimus=SopimusTyyppi.KUUKAUSI)
    ajoneuvo = Ajoneuvo(tuotanto_id=t.id, nimi="Vieras auto")
    lokaatio = Lokaatio(tuotanto_id=t.id, nimi="Vieras lokaatio")
    paiva = Kuvauspaiva(tuotanto_id=t.id, pvm=date(2026, 7, 10), call_time=time(8, 0))
    db.add_all([henkilo, kuski, ajoneuvo, lokaatio, paiva])
    await db.flush()
    ph = PaivaHenkilo(paiva_id=paiva.id, henkilo_id=henkilo.id)
    pk = PaivaKuski(paiva_id=paiva.id, kuski_id=kuski.id, ajoneuvo_id=ajoneuvo.id)
    pl = PaivaLokaatio(paiva_id=paiva.id, lokaatio_id=lokaatio.id)
    tehtava = Tehtava(
        paiva_id=paiva.id, tyyppi=TehtavaTyyppi.HENKILO, nimi="Vieras nouto",
        mista_osoite="A", mihin_osoite="B",
    )
    versio = AjolistaVersio(paiva_id=paiva.id, versio_nro=1, kokonaiskustannus_eur=10.0)
    db.add_all([ph, pk, pl, tehtava, versio])
    await db.flush()
    keikka = Keikka(
        versio_id=versio.id, tehtava_id=tehtava.id, paiva_kuski_id=pk.id,
        nouto_klo=time(7, 0), jatto_klo=time(7, 15), jarjestys=1,
    )
    db.add(keikka)
    await db.commit()
    return {
        "tuotanto": t.id, "henkilo": henkilo.id, "kuski": kuski.id, "ajoneuvo": ajoneuvo.id,
        "lokaatio": lokaatio.id, "paiva": paiva.id, "paiva_henkilo": ph.id, "paiva_kuski": pk.id,
        "paiva_lokaatio": pl.id, "tehtava": tehtava.id, "versio": versio.id, "keikka": keikka.id,
    }


def _vieraat_pyynnot(v: dict[str, int], oma: int) -> list[tuple[str, str, dict | None]]:
    """(metodi, polku, runko) jokaiselle reitille, joka osoittaa toisen
    tuotannon dataan. Rungot ovat kelvollisia, jotta 404 tulee
    omistustarkistuksesta eikä validoinnista (422)."""
    t, p = v["tuotanto"], v["paiva"]
    henkilo = {"tuotanto_id": t, "tyyppi": "cast", "nimi": "X"}
    kuski = {"tuotanto_id": t, "nimi": "X", "sopimus": "kuukausi"}
    nimi_t = {"tuotanto_id": t, "nimi": "X"}
    paiva = {"tuotanto_id": t, "pvm": "2026-08-01", "call_time": "08:00:00"}
    ph = {"paiva_id": p, "henkilo_id": v["henkilo"]}
    pk = {"paiva_id": p, "kuski_id": v["kuski"]}
    pl = {"paiva_id": p, "lokaatio_id": v["lokaatio"]}
    teht = {"paiva_id": p, "tyyppi": "henkilo", "nimi": "X", "mista_osoite": "A", "mihin_osoite": "B"}
    return [
        # tuotanto
        ("GET", f"/tuotannot/{t}", None),
        ("PUT", f"/tuotannot/{t}", {"nimi": "Kaapattu"}),
        ("DELETE", f"/tuotannot/{t}", None),
        ("POST", f"/tuotannot/{t}/geokoodaa", None),
        # perusdata: haku, käyttö, päivitys, poisto, listaus toisen tuotannon suodattimella
        *[
            pyynto
            for polku, avain, runko in [
                ("henkilot", "henkilo", henkilo),
                ("kuskit", "kuski", kuski),
                ("lokaatiot", "lokaatio", nimi_t),
            ]
            for pyynto in [
                ("GET", f"/{polku}/{v[avain]}", None),
                ("GET", f"/{polku}/{v[avain]}?sisalla_passiiviset=true", None),
                ("GET", f"/{polku}/{v[avain]}/kaytto", None),
                ("PUT", f"/{polku}/{v[avain]}", {**runko, "tuotanto_id": oma}),
                ("DELETE", f"/{polku}/{v[avain]}", None),
                ("GET", f"/{polku}?tuotanto_id={t}", None),
                ("POST", f"/{polku}", runko),
            ]
        ],
        ("GET", f"/ajoneuvot/{v['ajoneuvo']}", None),
        ("PUT", f"/ajoneuvot/{v['ajoneuvo']}", {**nimi_t, "tuotanto_id": oma}),
        ("DELETE", f"/ajoneuvot/{v['ajoneuvo']}", None),
        ("GET", f"/ajoneuvot?tuotanto_id={t}", None),
        ("POST", "/ajoneuvot", nimi_t),
        ("GET", f"/kuvauspaivat/{p}", None),
        ("PUT", f"/kuvauspaivat/{p}", {**paiva, "tuotanto_id": oma}),
        ("DELETE", f"/kuvauspaivat/{p}", None),
        ("GET", f"/kuvauspaivat?tuotanto_id={t}", None),
        ("POST", "/kuvauspaivat", paiva),
        # päivän rivit
        *[
            pyynto
            for polku, avain, runko in [
                ("paiva-henkilot", "paiva_henkilo", ph),
                ("paiva-kuskit", "paiva_kuski", pk),
                ("paiva-lokaatiot", "paiva_lokaatio", pl),
                ("tehtavat", "tehtava", teht),
            ]
            for pyynto in [
                ("GET", f"/{polku}/{v[avain]}", None),
                ("PUT", f"/{polku}/{v[avain]}", runko),
                ("DELETE", f"/{polku}/{v[avain]}", None),
                ("GET", f"/{polku}?paiva_id={p}", None),
                ("POST", f"/{polku}", runko),
            ]
        ],
        # päivän toiminnot, versiot, keikat
        ("POST", f"/paivat/{p}/generoi-tehtavat", None),
        ("GET", f"/paivat/{p}/optimointi", None),
        ("POST", f"/paivat/{p}/optimoi", {"aikaraja_s": 1}),
        ("GET", f"/versiot/{v['versio']}", None),
        ("GET", f"/versiot?paiva_id={p}", None),
        ("POST", f"/versiot/{v['versio']}/julkaise", None),
        ("GET", f"/versiot/{v['versio']}/diff/{v['versio']}", None),
        ("GET", f"/keikat?versio_id={v['versio']}", None),
        ("PATCH", f"/keikat/{v['keikka']}/kuittaa", None),
    ]


async def test_toisen_tuotannon_data_404_kaikilla_reiteilla(client, db_session, tuotanto_id):
    v = await _seed_toinen_tuotanto(db_session)
    pyynnot = _vieraat_pyynnot(v, tuotanto_id)

    vaarin = []
    for metodi, polku, runko in pyynnot:
        vastaus = await client.request(metodi, polku, json=runko)
        if vastaus.status_code != 404:
            vaarin.append(f"{metodi} {polku} -> {vastaus.status_code} {vastaus.text[:120]}")
    assert not vaarin, "\n".join(vaarin)

    # Mikään yritys ei muuttanut toisen tuotannon dataa.
    db_session.expire_all()
    assert (await db_session.get(Tuotanto, v["tuotanto"])).nimi == "Toinen tuotanto"
    assert (await db_session.get(Henkilo, v["henkilo"])).aktiivinen is True
    assert (await db_session.get(Kuski, v["kuski"])).aktiivinen is True
    assert (await db_session.get(Ajoneuvo, v["ajoneuvo"])) is not None
    assert (await db_session.get(PaivaHenkilo, v["paiva_henkilo"])) is not None
    assert (await db_session.get(AjolistaVersio, v["versio"])).julkaistu is False
    assert (await db_session.get(Keikka, v["keikka"])).kuitattu is False


async def test_listaukset_ilman_suodatinta_nayttavat_vain_oman_tuotannon(client, db_session, tuotanto_id):
    await _seed_toinen_tuotanto(db_session)
    # Sama ketju omaan tuotantoon API:n kautta
    oma_henkilo = (await client.post(
        "/henkilot", json={"tuotanto_id": tuotanto_id, "tyyppi": "cast", "nimi": "Oma"}
    )).json()["id"]

    assert [t["id"] for t in (await client.get("/tuotannot")).json()] == [tuotanto_id]
    assert [h["id"] for h in (await client.get("/henkilot")).json()] == [oma_henkilo]
    for polku in (
        "/kuskit", "/ajoneuvot", "/lokaatiot", "/kuvauspaivat", "/paiva-henkilot",
        "/paiva-kuskit", "/paiva-lokaatiot", "/tehtavat", "/versiot", "/keikat",
    ):
        vastaus = await client.get(polku)
        assert vastaus.status_code == 200, polku
        assert vastaus.json() == [], polku


async def test_omaan_paivaan_ei_voi_liittaa_toisen_tuotannon_riveja(client, db_session, tuotanto_id):
    v = await _seed_toinen_tuotanto(db_session)
    paiva_id = (await client.post(
        "/kuvauspaivat", json={"tuotanto_id": tuotanto_id, "pvm": "2026-07-10", "call_time": "08:00:00"}
    )).json()["id"]

    for polku, runko in [
        ("/paiva-henkilot", {"paiva_id": paiva_id, "henkilo_id": v["henkilo"]}),
        ("/paiva-kuskit", {"paiva_id": paiva_id, "kuski_id": v["kuski"]}),
        ("/paiva-lokaatiot", {"paiva_id": paiva_id, "lokaatio_id": v["lokaatio"]}),
        ("/tehtavat", {
            "paiva_id": paiva_id, "tyyppi": "henkilo", "nimi": "X", "mista_osoite": "A",
            "mihin_osoite": "B", "henkilo_id": v["henkilo"],
        }),
        ("/tehtavat", {
            "paiva_id": paiva_id, "tyyppi": "henkilo", "nimi": "X", "mista_osoite": "A",
            "mihin_osoite": "B", "lukittu_kuski_id": v["kuski"],
        }),
    ]:
        vastaus = await client.post(polku, json=runko)
        assert vastaus.status_code == 404, (polku, runko, vastaus.text)


async def test_oman_tuotannon_kayttaja_nakee_saman_datan(client, db_session, kirjaudu):
    """Vastakoe: toisen tuotannon oma käyttäjä näkee datansa normaalisti."""
    v = await _seed_toinen_tuotanto(db_session)
    otsakkeet = await kirjaudu(tuotanto_id=v["tuotanto"])
    vastaus = await client.get(f"/henkilot/{v['henkilo']}", headers=otsakkeet)
    assert vastaus.status_code == 200
    vastaus = await client.get(f"/keikat?versio_id={v['versio']}", headers=otsakkeet)
    assert [k["id"] for k in vastaus.json()] == [v["keikka"]]

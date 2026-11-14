"""K1: kirjautuminen (POST /auth/kirjaudu, GET /auth/mina), token,
asetusten JWT-tarkistus, luo_kayttaja-työkalu ja seedin demokäyttäjät."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.auth import ALGORITMI, hashaa_salasana, luo_token, pura_token, VirheellinenToken
from app.config import DEV_JWT_SECRET, Settings, settings
from app.luo_kayttaja import LuontiVirhe, luo_kayttaja
from app.models import Kayttaja, KayttajaRooli, Kuski, SopimusTyyppi, Tuotanto
from app.routers.auth import VAARA_TUNNUS

SALASANA = "oikea-salasana-123"


async def _kayttaja(db, *, email="tanja@example.com", rooli=KayttajaRooli.TUOTANTO,
                    salasana: str | None = SALASANA, aktiivinen=True, tuotanto_id=None,
                    kuski_id=None) -> Kayttaja:
    if tuotanto_id is None:
        tuotanto = Tuotanto(nimi="Testituotanto")
        db.add(tuotanto)
        await db.flush()
        tuotanto_id = tuotanto.id
    k = Kayttaja(
        tuotanto_id=tuotanto_id, email=email, nimi="Tanja", rooli=rooli, kuski_id=kuski_id,
        salasana_hash=hashaa_salasana(salasana) if salasana else None, aktiivinen=aktiivinen,
    )
    db.add(k)
    await db.commit()
    await db.refresh(k)
    return k


async def _kirjaudu(client, email="tanja@example.com", salasana=SALASANA):
    return await client.post("/auth/kirjaudu", json={"email": email, "salasana": salasana})


# ---------------------------------------------------------------------------
# POST /auth/kirjaudu
# ---------------------------------------------------------------------------


async def test_kirjautuminen_oikealla_salasanalla(client, db_session):
    k = await _kayttaja(db_session)

    r = await _kirjaudu(client)

    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert data["voimassa_s"] == 12 * 3600
    assert data["kayttaja"]["id"] == k.id
    assert data["kayttaja"]["rooli"] == "tuotanto"
    assert data["kayttaja"]["viimeksi_kirjautunut"] is not None
    assert "salasana_hash" not in data["kayttaja"]


async def test_email_ei_ole_kirjainkokoriippuvainen(client, db_session):
    await _kayttaja(db_session)
    r = await _kirjaudu(client, email="  Tanja@Example.COM ")
    assert r.status_code == 200


@pytest.mark.parametrize(
    "tilanne",
    ["vaara_salasana", "tuntematon_email", "passivoitu", "ei_salasanaa"],
)
async def test_epaonnistunut_kirjautuminen_antaa_aina_saman_401(client, db_session, tilanne):
    email, salasana = "tanja@example.com", SALASANA
    if tilanne == "vaara_salasana":
        await _kayttaja(db_session)
        salasana = "vaara-salasana"
    elif tilanne == "tuntematon_email":
        await _kayttaja(db_session)
        email = "joku@example.com"
    elif tilanne == "passivoitu":
        await _kayttaja(db_session, aktiivinen=False)
    elif tilanne == "ei_salasanaa":
        await _kayttaja(db_session, salasana=None)

    r = await _kirjaudu(client, email=email, salasana=salasana)

    assert r.status_code == 401
    assert r.json() == {"detail": VAARA_TUNNUS}


async def test_puuttuvat_kentat_422(client):
    r = await client.post("/auth/kirjaudu", json={"email": "tanja@example.com"})
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Tokenin sisältö
# ---------------------------------------------------------------------------


async def test_token_sisaltaa_kayttajan_roolin_ja_tuotannon(client, db_session):
    k = await _kayttaja(db_session, rooli=KayttajaRooli.KOORDI)

    token = (await _kirjaudu(client)).json()["access_token"]

    payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITMI])
    assert payload["sub"] == str(k.id)
    assert payload["rooli"] == "koordi"
    assert payload["tuotanto_id"] == k.tuotanto_id
    assert payload["exp"] - payload["iat"] == 12 * 3600
    assert "salasana" not in str(payload) and "email" not in payload

    sisalto = pura_token(token)
    assert (sisalto.kayttaja_id, sisalto.rooli, sisalto.tuotanto_id) == (
        k.id, KayttajaRooli.KOORDI, k.tuotanto_id,
    )


async def test_vanhentunut_token_hylataan(db_session):
    k = await _kayttaja(db_session)
    token = luo_token(k, nyt=datetime.now(UTC) - timedelta(hours=13))
    with pytest.raises(VirheellinenToken):
        pura_token(token)


async def test_vaaralla_salaisuudella_tai_ilman_allekirjoitusta_hylataan(db_session):
    k = await _kayttaja(db_session)
    nyt = datetime.now(UTC)
    payload = {"sub": str(k.id), "rooli": "tuotanto", "tuotanto_id": k.tuotanto_id,
               "iat": nyt, "exp": nyt + timedelta(hours=1)}
    vaara = jwt.encode(payload, "toinen-salaisuus-joka-on-tarpeeksi-pitka-32", algorithm="HS256")
    allekirjoittamaton = jwt.encode(payload, None, algorithm="none")
    for token in (vaara, allekirjoittamaton, "ei-token", ""):
        with pytest.raises(VirheellinenToken):
            pura_token(token)


# ---------------------------------------------------------------------------
# GET /auth/mina
# ---------------------------------------------------------------------------


async def test_mina_palauttaa_kirjautuneen_ilman_hashia(client, db_session):
    k = await _kayttaja(db_session)
    token = (await _kirjaudu(client)).json()["access_token"]

    r = await client.get("/auth/mina", headers={"Authorization": f"Bearer {token}"})

    assert r.status_code == 200
    data = r.json()
    assert data["id"] == k.id and data["email"] == "tanja@example.com"
    assert "salasana_hash" not in data


async def test_mina_ilman_tokenia_tai_rikkinaisella_401(client, db_session):
    k = await _kayttaja(db_session)
    vanha = luo_token(k, nyt=datetime.now(UTC) - timedelta(hours=13))
    for otsakkeet in ({}, {"Authorization": "Bearer roskaa"}, {"Authorization": f"Bearer {vanha}"}):
        r = await client.get("/auth/mina", headers=otsakkeet)
        assert r.status_code == 401
        assert r.headers["www-authenticate"] == "Bearer"


async def test_passivoitu_kesken_istunnon_menettaa_paasyn(client, db_session):
    k = await _kayttaja(db_session)
    token = (await _kirjaudu(client)).json()["access_token"]

    k.aktiivinen = False
    await db_session.commit()

    r = await client.get("/auth/mina", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# JWT_SECRET ja AJURI_YMPARISTO
# ---------------------------------------------------------------------------


def test_dev_ymparistossa_oletussalaisuus_kelpaa(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    s = Settings(_env_file=None, ajuri_ymparisto="dev")
    assert s.jwt_secret == DEV_JWT_SECRET


def test_prod_ilman_salaisuutta_kaataa_kaynnistyksen(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="JWT_SECRET puuttuu"):
        Settings(_env_file=None, ajuri_ymparisto="prod")


def test_prod_salaisuus_ymparistomuuttujasta(monkeypatch):
    monkeypatch.setenv("AJURI_YMPARISTO", "prod")
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    s = Settings(_env_file=None)
    assert s.ajuri_ymparisto == "prod" and s.jwt_secret == "x" * 48


# ---------------------------------------------------------------------------
# python -m app.luo_kayttaja
# ---------------------------------------------------------------------------


async def test_luo_kayttaja_ja_kirjautuminen_toimii(client, db_session):
    db_session.add(Tuotanto(nimi="Ainoa tuotanto"))
    await db_session.commit()

    k = await luo_kayttaja(db_session, email="Tanja@Example.com", rooli=KayttajaRooli.TUOTANTO,
                           salasana=SALASANA)

    assert k.email == "tanja@example.com" and k.nimi == "tanja" and k.aktiivinen
    assert k.salasana_hash.startswith("$argon2")
    assert (await _kirjaudu(client)).status_code == 200


async def test_luo_kayttaja_virheet(db_session):
    t1, t2 = Tuotanto(nimi="A"), Tuotanto(nimi="B")
    db_session.add_all([t1, t2])
    await db_session.flush()
    kuski = Kuski(tuotanto_id=t1.id, nimi="Kuski", sopimus=SopimusTyyppi.KUUKAUSI)
    db_session.add(kuski)
    await db_session.commit()

    perus = dict(email="a@example.com", rooli=KayttajaRooli.TUOTANTO, salasana=SALASANA)
    with pytest.raises(LuontiVirhe, match="tuotanto-id"):  # kaksi tuotantoa, ei valintaa
        await luo_kayttaja(db_session, **perus)
    with pytest.raises(LuontiVirhe, match="vähintään"):
        await luo_kayttaja(db_session, **{**perus, "salasana": "lyhyt"}, tuotanto_id=t1.id)
    with pytest.raises(LuontiVirhe, match="kuski-id"):
        await luo_kayttaja(db_session, **{**perus, "rooli": KayttajaRooli.KUSKI}, tuotanto_id=t1.id)
    with pytest.raises(LuontiVirhe, match="Kuskia"):  # kuski väärästä tuotannosta
        await luo_kayttaja(db_session, **{**perus, "rooli": KayttajaRooli.KUSKI},
                           tuotanto_id=t2.id, kuski_id=kuski.id)

    await luo_kayttaja(db_session, **perus, tuotanto_id=t1.id)
    with pytest.raises(LuontiVirhe, match="jo olemassa"):
        await luo_kayttaja(db_session, **{**perus, "email": "A@example.com"}, tuotanto_id=t1.id)


# ---------------------------------------------------------------------------
# Seedin demokäyttäjät
# ---------------------------------------------------------------------------


async def test_seed_luo_demokayttajat_idempotentisti(client, db_session):
    from app.seed import DEMOKAYTTAJAT, seed

    await seed(db_session)
    hashit = {k.email: k.salasana_hash for k in
              (await db_session.execute(Kayttaja.__table__.select())).all()}
    await seed(db_session)  # uudelleenajo ei vaihda hasheja eikä luo tuplia
    rivit = (await db_session.execute(Kayttaja.__table__.select())).all()
    assert len(rivit) == len(DEMOKAYTTAJAT)
    assert {r.email: r.salasana_hash for r in rivit} == hashit

    for email, _nimi, rooli, salasana in DEMOKAYTTAJAT:
        r = await _kirjaudu(client, email=email, salasana=salasana)
        assert r.status_code == 200, email
        kayttaja = r.json()["kayttaja"]
        assert kayttaja["rooli"] == rooli.value
        assert (kayttaja["kuski_id"] is not None) == (rooli == KayttajaRooli.KUSKI)

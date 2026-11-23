"""M2: demotila. DEMO=true näyttää kirjautumissivulla demonapit
(GET /auth/demo) ja sallii kirjautumisen seedin demokäyttäjäksi ilman
salasanaa (POST /auth/demo). Ilman DEMO=true kumpaakaan ei ole."""

import pytest
from sqlalchemy import select

from app.auth import pura_token
from app.config import Settings, settings
from app.models import Kayttaja, KayttajaRooli
from app.routers.auth import DEMO_EI_KAYTOSSA, DEMODATAA_EI_OLE
from app.seed import seed


@pytest.fixture
def client(anon_client):
    """Demotestit kirjautuvat itse: kirjautumaton asiakas."""
    return anon_client


@pytest.fixture
def demo_paalla(monkeypatch):
    monkeypatch.setattr(settings, "demo", True)


def test_demo_on_oletuksena_pois():
    assert Settings().demo is False


# ---------------------------------------------------------------------------
# Ilman DEMO=true
# ---------------------------------------------------------------------------


async def test_ilman_demoa_napit_eivat_nay(client, db_session):
    await seed(db_session)  # demokäyttäjät ovat olemassa, mutta tila on pois

    r = await client.get("/auth/demo")

    assert r.status_code == 200
    assert r.json() == {"kaytossa": False, "roolit": []}


async def test_ilman_demoa_demokirjautuminen_404(client, db_session):
    await seed(db_session)

    r = await client.post("/auth/demo", json={"rooli": "tuotanto"})

    assert r.status_code == 404
    assert r.json()["detail"] == DEMO_EI_KAYTOSSA
    assert "access_token" not in r.json()


# ---------------------------------------------------------------------------
# DEMO=true
# ---------------------------------------------------------------------------


async def test_demo_paalla_napit_tuotannolle_ja_kuskille(client, db_session, demo_paalla):
    await seed(db_session)

    r = await client.get("/auth/demo")

    assert r.status_code == 200
    assert r.json() == {"kaytossa": True, "roolit": ["tuotanto", "kuski"]}


async def test_demo_paalla_ilman_seedia_napit_eivat_nay(client, demo_paalla):
    r = await client.get("/auth/demo")

    assert r.json() == {"kaytossa": False, "roolit": []}


@pytest.mark.parametrize("rooli", ["tuotanto", "kuski"])
async def test_demokirjautuminen(client, db_session, demo_paalla, rooli):
    tuotanto, _ = await seed(db_session)

    r = await client.post("/auth/demo", json={"rooli": rooli})

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["kayttaja"]["rooli"] == rooli
    assert data["kayttaja"]["tuotanto_id"] == tuotanto.id
    assert "salasana_hash" not in data["kayttaja"]
    sisalto = pura_token(data["access_token"])
    assert sisalto.rooli == KayttajaRooli(rooli)
    assert sisalto.tuotanto_id == tuotanto.id

    # Token kelpaa tavallisille reiteille
    otsakkeet = {"Authorization": f"Bearer {data['access_token']}"}
    mina = await client.get("/auth/mina", headers=otsakkeet)
    assert mina.status_code == 200
    assert mina.json()["email"] == data["kayttaja"]["email"]
    assert (await client.get("/kuvauspaivat", headers=otsakkeet)).status_code == 200


async def test_demokuski_ei_saa_muokata(client, db_session, demo_paalla):
    await seed(db_session)
    token = (await client.post("/auth/demo", json={"rooli": "kuski"})).json()["access_token"]

    r = await client.post(
        "/henkilot", json={"nimi": "X"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert r.status_code == 403


async def test_demokirjautuminen_kirjaa_aikaleiman(client, db_session, demo_paalla):
    await seed(db_session)

    data = (await client.post("/auth/demo", json={"rooli": "tuotanto"})).json()

    db_session.expire_all()
    kayttaja = await db_session.get(Kayttaja, data["kayttaja"]["id"])
    assert kayttaja.viimeksi_kirjautunut is not None


async def test_koordille_ei_ole_demonappia(client, db_session, demo_paalla):
    await seed(db_session)

    r = await client.post("/auth/demo", json={"rooli": "koordi"})

    assert r.status_code == 422


async def test_tuntematon_rooli_422(client, demo_paalla):
    r = await client.post("/auth/demo", json={"rooli": "admin"})

    assert r.status_code == 422


async def test_demo_paalla_ilman_seedia_503(client, demo_paalla):
    r = await client.post("/auth/demo", json={"rooli": "tuotanto"})

    assert r.status_code == 503
    assert r.json()["detail"] == DEMODATAA_EI_OLE


async def test_passivoitu_demokayttaja_ei_paase(client, db_session, demo_paalla):
    await seed(db_session)
    k = (
        await db_session.execute(select(Kayttaja).where(Kayttaja.rooli == KayttajaRooli.KUSKI))
    ).scalar_one()
    k.aktiivinen = False
    await db_session.commit()

    assert (await client.post("/auth/demo", json={"rooli": "kuski"})).status_code == 503
    assert (await client.get("/auth/demo")).json()["roolit"] == ["tuotanto"]


async def test_demokirjautumisella_on_pyyntoraja(client, db_session, demo_paalla, monkeypatch):
    await seed(db_session)
    monkeypatch.setattr(settings, "rajoitus_kirjautuminen", "2/minute")

    tilat = [
        (await client.post("/auth/demo", json={"rooli": "tuotanto"})).status_code
        for _ in range(3)
    ]

    assert tilat == [200, 200, 429]

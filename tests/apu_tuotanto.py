"""Apu testeille, jotka luovat dataa suoraan kantaan (db_session).

K2:sta lähtien käyttäjä näkee vain oman tuotantonsa datan, joten datan
pitää kuulua kirjautuneen testikäyttäjän tuotantoon. `client`-fixture
luo sen (tests/conftest.py, `tuotanto_id`); tämä hakee sen ja asettaa
annetut kentät, esim. `await hae_testituotanto(db_session, tuntihinta_eur=20.0)`.
"""

from sqlalchemy import select

from app.models import Tuotanto


async def hae_testituotanto(db_session, **kentat) -> Tuotanto:
    tuotanto = (
        await db_session.execute(select(Tuotanto).order_by(Tuotanto.id).limit(1))
    ).scalar_one()
    for kentta, arvo in kentat.items():
        setattr(tuotanto, kentta, arvo)
    await db_session.flush()
    return tuotanto


async def oma_tuotanto_id(client) -> int:
    """Kirjautuneen käyttäjän tuotannon id (GET /auth/mina)."""
    vastaus = await client.get("/auth/mina")
    assert vastaus.status_code == 200, vastaus.text
    return vastaus.json()["tuotanto_id"]

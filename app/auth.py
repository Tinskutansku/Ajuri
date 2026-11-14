"""Kirjautuminen: salasanojen hashays (argon2) ja JWT-tokenit (HS256).

Token sisältää käyttäjä-id:n (`sub`), roolin ja tuotanto-id:n. Kohdassa
K2 `app/rooli.py:nykyinen_rooli` alkaa lukea roolin tästä tokenista
X-Rooli-otsakkeen sijaan; tässä vaiheessa token on käytössä vain
`/auth`-reiteillä.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import settings
from app.models import Kayttaja, KayttajaRooli

ALGORITMI = "HS256"

_hasher = PasswordHasher()

# Hash, jota vasten tuntemattoman emailin salasana "tarkistetaan", jotta
# vastausaika ei paljasta, onko email olemassa.
_TYHJA_HASH = _hasher.hash("ajuri-ei-kayttajaa")


def hashaa_salasana(salasana: str) -> str:
    return _hasher.hash(salasana)


def tarkista_salasana(salasana_hash: str | None, salasana: str) -> bool:
    """True jos salasana täsmää. Puuttuva hash (käyttäjälle ei ole
    asetettu salasanaa) ajaa silti tarkistuksen tyhjää hashia vasten,
    jotta aika on sama kuin väärällä salasanalla."""
    try:
        _hasher.verify(salasana_hash or _TYHJA_HASH, salasana)
    except (VerificationError, InvalidHashError):
        return False
    return salasana_hash is not None


def tarvitseeko_uudelleenhashin(salasana_hash: str) -> bool:
    """argon2-parametrit voivat kasvaa kirjastopäivityksissä; vanha hash
    päivitetään seuraavan onnistuneen kirjautumisen yhteydessä."""
    return _hasher.check_needs_rehash(salasana_hash)


@dataclass(frozen=True)
class TokenSisalto:
    kayttaja_id: int
    rooli: KayttajaRooli
    tuotanto_id: int


def luo_token(kayttaja: Kayttaja, *, nyt: datetime | None = None) -> str:
    nyt = nyt or datetime.now(UTC)
    payload = {
        "sub": str(kayttaja.id),  # JWT-standardi: sub on merkkijono
        "rooli": kayttaja.rooli.value,
        "tuotanto_id": kayttaja.tuotanto_id,
        "iat": nyt,
        "exp": nyt + timedelta(hours=settings.jwt_voimassa_h),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITMI)


class VirheellinenToken(Exception):
    """Token puuttuu, on vanhentunut, väärin allekirjoitettu tai rikki."""


def pura_token(token: str) -> TokenSisalto:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITMI],  # ei koskaan "none" tai muuta algoritmia
            options={"require": ["sub", "exp", "iat"]},
        )
        return TokenSisalto(
            kayttaja_id=int(payload["sub"]),
            rooli=KayttajaRooli(payload["rooli"]),
            tuotanto_id=int(payload["tuotanto_id"]),
        )
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as e:
        raise VirheellinenToken(str(e)) from e

"""Komentorivityökalu käyttäjän luontiin (esim. ensimmäinen tuotantokäyttäjä).

Käyttö:
    python -m app.luo_kayttaja --email tanja@example.com --rooli tuotanto
    python -m app.luo_kayttaja --email kuski@example.com --rooli kuski --kuski-id 3

Salasana kysytään piilotettuna kahteen kertaan (ei koskaan komentoriville,
ettei se jää shell-historiaan). --tuotanto-id voi jättää pois, jos kannassa
on tasan yksi tuotanto. --nimi oletuksena emailin alkuosa.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import hashaa_salasana
from app.models import Kayttaja, KayttajaRooli, Kuski, Tuotanto

SALASANAN_MIN_PITUUS = 10


class LuontiVirhe(Exception):
    """Käyttäjälle näytettävä virhe (ei tracebackia)."""


async def luo_kayttaja(
    db: AsyncSession,
    *,
    email: str,
    rooli: KayttajaRooli,
    salasana: str,
    nimi: str | None = None,
    tuotanto_id: int | None = None,
    kuski_id: int | None = None,
) -> Kayttaja:
    email = email.strip().lower()
    if "@" not in email:
        raise LuontiVirhe(f"Virheellinen sähköposti: {email!r}")
    if len(salasana) < SALASANAN_MIN_PITUUS:
        raise LuontiVirhe(f"Salasanan pitää olla vähintään {SALASANAN_MIN_PITUUS} merkkiä.")

    olemassa = (
        await db.execute(select(Kayttaja).where(func.lower(Kayttaja.email) == email))
    ).scalar_one_or_none()
    if olemassa is not None:
        raise LuontiVirhe(f"Käyttäjä {email} on jo olemassa (id={olemassa.id}).")

    if tuotanto_id is None:
        tuotannot = (await db.execute(select(Tuotanto).order_by(Tuotanto.id))).scalars().all()
        if len(tuotannot) != 1:
            lista = ", ".join(f"{t.id}={t.nimi}" for t in tuotannot) or "ei yhtään"
            raise LuontiVirhe(f"Anna --tuotanto-id. Tuotannot: {lista}")
        tuotanto_id = tuotannot[0].id
    elif await db.get(Tuotanto, tuotanto_id) is None:
        raise LuontiVirhe(f"Tuotantoa {tuotanto_id} ei ole.")

    if rooli == KayttajaRooli.KUSKI:
        if kuski_id is None:
            raise LuontiVirhe("KUSKI-roolille pitää antaa --kuski-id.")
        kuski = await db.get(Kuski, kuski_id)
        if kuski is None or kuski.tuotanto_id != tuotanto_id:
            raise LuontiVirhe(f"Kuskia {kuski_id} ei ole tuotannossa {tuotanto_id}.")
    elif kuski_id is not None:
        raise LuontiVirhe("--kuski-id kuuluu vain KUSKI-roolille.")

    kayttaja = Kayttaja(
        tuotanto_id=tuotanto_id,
        email=email,
        nimi=nimi or email.split("@")[0],
        rooli=rooli,
        kuski_id=kuski_id,
        salasana_hash=hashaa_salasana(salasana),
        aktiivinen=True,
    )
    db.add(kayttaja)
    await db.commit()
    await db.refresh(kayttaja)
    return kayttaja


def _kysy_salasana() -> str:
    salasana = getpass.getpass("Salasana: ")
    if getpass.getpass("Salasana uudelleen: ") != salasana:
        raise LuontiVirhe("Salasanat eivät täsmää.")
    return salasana


async def _main(args: argparse.Namespace) -> None:
    from app.database import AsyncSessionLocal

    salasana = _kysy_salasana()
    async with AsyncSessionLocal() as db:
        kayttaja = await luo_kayttaja(
            db,
            email=args.email,
            rooli=KayttajaRooli(args.rooli),
            salasana=salasana,
            nimi=args.nimi,
            tuotanto_id=args.tuotanto_id,
            kuski_id=args.kuski_id,
        )
    print(f"Luotu: {kayttaja.email} (id={kayttaja.id}, rooli={kayttaja.rooli.value}, "
          f"tuotanto={kayttaja.tuotanto_id})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Luo AJURI-käyttäjä.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--rooli", required=True, choices=[r.value for r in KayttajaRooli])
    parser.add_argument("--nimi")
    parser.add_argument("--tuotanto-id", type=int)
    parser.add_argument("--kuski-id", type=int)
    args = parser.parse_args(argv)
    try:
        asyncio.run(_main(args))
    except LuontiVirhe as e:
        print(f"Virhe: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

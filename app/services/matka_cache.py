"""Ajoaikojen välimuisti: kysyy ensin Matka-taulusta, hakee puuttuvat
parit reititys-API:sta yhtenä matriisikutsuna ja tallentaa ne."""

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Matka
from app.services.router_client import RouterClient

Piste = tuple[float, float]


def pyorista_piste(piste: Piste) -> Piste:
    lat, lon = piste
    return (round(lat, 4), round(lon, 4))


async def hae_ajoajat(
    db: AsyncSession,
    pisteet: list[Piste],
    router: RouterClient,
    lahde: str = "osrm",
) -> dict[tuple[Piste, Piste], tuple[int, float]]:
    """Palauttaa {(mista, mihin): (ajoaika_s, matka_m)} kaikille annettujen
    pisteiden pareille. mista == mihin -parit eivät kysy välimuistia eikä
    API:a, vaan palautuvat suoraan (0, 0.0)."""
    yksilolliset = sorted({pyorista_piste(p) for p in pisteet})
    tulos: dict[tuple[Piste, Piste], tuple[int, float]] = {
        (a, a): (0, 0.0) for a in yksilolliset
    }

    parit = [(a, b) for a in yksilolliset for b in yksilolliset if a != b]
    if not parit:
        return tulos

    ehto = tuple_(Matka.mista_lat, Matka.mista_lon, Matka.mihin_lat, Matka.mihin_lon).in_(
        [(a[0], a[1], b[0], b[1]) for a, b in parit]
    )
    result = await db.execute(select(Matka).where(ehto))
    for rivi in result.scalars():
        avain = ((rivi.mista_lat, rivi.mista_lon), (rivi.mihin_lat, rivi.mihin_lon))
        tulos[avain] = (rivi.ajoaika_s, rivi.matka_m)

    puuttuvat = [p for p in parit if p not in tulos]
    if puuttuvat:
        kestot, matkat = await router.matriisi(yksilolliset)
        uudet_rivit = []
        for i, a in enumerate(yksilolliset):
            for j, b in enumerate(yksilolliset):
                if a == b or (a, b) in tulos:
                    continue
                ajoaika_s, matka_m = kestot[i][j], matkat[i][j]
                tulos[(a, b)] = (ajoaika_s, matka_m)
                uudet_rivit.append(
                    Matka(
                        mista_lat=a[0],
                        mista_lon=a[1],
                        mihin_lat=b[0],
                        mihin_lon=b[1],
                        ajoaika_s=ajoaika_s,
                        matka_m=matka_m,
                        lahde=lahde,
                    )
                )
        db.add_all(uudet_rivit)
        await db.commit()

    return tulos

"""Regressiotesti: ajolista_optimoija.py:n vakiodata (17 tehtävää, 5 kuskia,
sekasopimuksin) sovitettuna optimoija-serviceen kiinteällä, prototyypin
ajoaika()-kaavalla esilasketulla matriisilla — ei tietokantaa, ei HTTP:tä.

Tämä on ainoa testi joka vahtii optimoinnin LAATUA eikä pelkkää muotoa:
odotus on että kaikki 17 tehtävää sijoitetaan ja että korkeintaan 3 kuskia
riittää niiden hoitamiseen (kuten alkuperäinen prototyyppi näyttää)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ajolista_optimoija as proto  # noqa: E402

from app.models import SopimusTyyppi
from app.services.optimoija import KuskiRow, OptimointiParametrit, TehtavaRow, ratkaise

# Sekasopimusjakauma viidelle prototyypin kuskille (spesifikaation kolme
# sopimustyyppiä edustettuna).
SOPIMUKSET = [
    SopimusTyyppi.KUUKAUSI,
    SopimusTyyppi.KUUKAUSI,
    SopimusTyyppi.PAIVA,
    SopimusTyyppi.TUNTI,
    SopimusTyyppi.TUNTI,
]


def _rakenna_ajoaikamatriisi() -> dict:
    nimet = list(proto.PAIKAT.keys())
    matriisi = {}
    for a in nimet:
        for b in nimet:
            if a == b:
                continue
            minuutit = proto.ajoaika(a, b)
            matriisi[(proto.PAIKAT[a], proto.PAIKAT[b])] = (minuutit * 60, 0.0)
    return matriisi


def _rakenna_tehtavat() -> list[TehtavaRow]:
    return [
        TehtavaRow(
            id=i,
            nimi=teht.nimi,
            mista=proto.PAIKAT[teht.mista],
            mihin=proto.PAIKAT[teht.mihin],
            henkiloita=teht.hloita,
            nouto_aikaisintaan=teht.nouto_aik,
            nouto_viimeistaan=teht.nouto_viim,
            perilla_aikaisintaan=teht.perilla_aik,
            perilla_viimeistaan=teht.perilla_viim,
        )
        for i, teht in enumerate(proto.TEHTAVAT)
    ]


def _rakenna_kuskit() -> list[KuskiRow]:
    return [
        KuskiRow(
            paiva_kuski_id=i + 1,
            kuski_id=i + 1,
            nimi=k.nimi,
            sopimus=SOPIMUKSET[i],
            tuntihinta=proto.TUNTIHINTA,
            paikkoja=k.paikkoja,
            aloitus=proto.PAIKAT[k.koti],
        )
        for i, k in enumerate(proto.KUSKIT)
    ]


def test_vakiopaiva_kaikki_sijoittuu_korkeintaan_kolmella_kuskilla():
    tehtavat = _rakenna_tehtavat()
    kuskit = _rakenna_kuskit()
    ajoaika = _rakenna_ajoaikamatriisi()

    tulos = ratkaise(tehtavat, kuskit, ajoaika, OptimointiParametrit(aikaraja_s=30))

    assert tulos.sijoittamatta == []

    kaytetyt = {k.paiva_kuski_id for k in tulos.keikat}
    assert len(kaytetyt) <= 3

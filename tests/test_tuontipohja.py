"""Rekisterin ladattava Excel-pohja (ROADMAP O2) kelpaa tuontiin sellaisenaan.

Pohja on `frontend/public/henkilot-pohja.xlsx`, ja sen luo
`scripts/luo_tuontipohja.py`. Jos tuonnin sarakealiaksia muutetaan niin,
ettei pohjan otsikko enää tunnistu, nämä testit kaatuvat.
"""

import io
from pathlib import Path

from openpyxl import load_workbook

from app.services.excel_tuonti import SARAKEALIAKSET, lue_henkilot

POHJA = Path(__file__).resolve().parent.parent / "frontend" / "public" / "henkilot-pohja.xlsx"


def test_pohjan_kaikki_sarakkeet_tunnistetaan():
    tulos = lue_henkilot(POHJA.read_bytes())
    kentat = [kentta for _, kentta in tulos.sarakkeet]
    assert None not in kentat
    # Pohjassa on jokainen tuonnin tuntema kenttä kerran.
    assert sorted(kentat) == sorted(set(SARAKEALIAKSET.values()))


def test_tyhja_pohja_ei_tuo_riveja():
    # Esimerkkirivit ovat Ohje-välilehdellä, eikä tuonti lue sitä.
    assert lue_henkilot(POHJA.read_bytes()).rivit == []


def test_taytetty_pohja_tuodaan_ja_alkunolla_sailyy():
    kirja = load_workbook(io.BytesIO(POHJA.read_bytes()))
    lehti = kirja["Henkilöt"]
    otsikot = [s.value for s in lehti[1]]
    arvot = {"Nimi": "Aino Näyttelijä", "Tyyppi": "cast", "Roolinimi": "Liisa", "Puhelin": "0401234567"}
    for sarake, otsikko in enumerate(otsikot, start=1):
        if otsikko in arvot:
            lehti.cell(row=2, column=sarake, value=arvot[otsikko])
    puskuri = io.BytesIO()
    kirja.save(puskuri)

    tulos = lue_henkilot(puskuri.getvalue())
    assert len(tulos.rivit) == 1
    henkilo = tulos.rivit[0].henkilo
    assert henkilo is not None
    assert henkilo.nimi == "Aino Näyttelijä"
    assert henkilo.tyyppi.value == "cast"
    assert henkilo.roolinimi == "Liisa"
    assert henkilo.puhelin == "0401234567"


def test_puhelinsarake_on_tekstimuotoinen():
    lehti = load_workbook(POHJA)["Henkilöt"]
    otsikot = [s.value for s in lehti[1]]
    sarake = otsikot.index("Puhelin") + 1
    assert lehti.cell(row=2, column=sarake).number_format == "@"

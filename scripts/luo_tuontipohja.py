"""Luo Rekisterin "Lataa pohjatiedosto" -napin Excel-pohjan (ROADMAP O2).

    python scripts/luo_tuontipohja.py

Kirjoittaa tiedoston `frontend/public/henkilot-pohja.xlsx`, jonka Vite
kopioi buildiin sellaisenaan. Tiedosto on versionhallinnassa, joten tätä
tarvitsee ajaa vain, kun sarakkeita muutetaan. `tests/test_tuontipohja.py`
varmistaa, että tuonti (`app/services/excel_tuonti.py`) tunnistaa pohjan
jokaisen sarakkeen.

Ensimmäinen välilehti on tyhjä täytettävä taulukko, koska tuonti lukee vain
sen. Esimerkkirivit ovat toisella välilehdellä, jotteivät ne päädy
rekisteriin, jos käyttäjä unohtaa poistaa ne.
"""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

KOHDE = Path(__file__).resolve().parent.parent / "frontend" / "public" / "henkilot-pohja.xlsx"

# (otsikko, leveys). Otsikot ovat SARAKEALIAKSET-taulun avaimia.
SARAKKEET = [
    ("Nimi", 26),
    ("Tyyppi", 10),
    ("Roolinimi", 18),
    ("Titteli", 18),
    ("Puhelin", 16),
    ("Osoite", 36),
    ("Huomiot", 30),
]
TAYTETTAVIA_RIVEJA = 500  # sama kuin tuonnin RIVIT_MAX

ESIMERKIT = [
    ["Aino Näyttelijä", "cast", "Liisa", None, "040 123 4567", "Mannerheimintie 1, Helsinki", None],
    ["Bertta Valo", "crew", None, "Valomies", "050 765 4321", "Hämeentie 5, Helsinki", "Oma auto usein"],
]

OHJE = [
    "Täytä henkilöt ensimmäiselle välilehdelle (Henkilöt). Vain se luetaan.",
    "Nimi on pakollinen. Muut sarakkeet saa jättää tyhjiksi.",
    "Tyyppi: cast (näyttelijä) tai crew (työryhmä). Tyhjä tyyppi tulkitaan",
    "  näyttelijäksi, jos roolinimi on annettu, muuten työryhmäksi.",
    "Puhelin-sarake on tekstimuotoinen, joten alkunolla säilyy.",
    "Osoitteiden koordinaatit haetaan tuonnin jälkeen Rekisterissä.",
    "Enintään 500 riviä ja 2 Mt. Sarakkeiden järjestyksellä ei ole väliä.",
    "",
    "Esimerkkirivit:",
]

OTSIKKO_FONTTI = Font(bold=True, color="FBF5E6")
OTSIKKO_TAUSTA = PatternFill("solid", fgColor="332416")


def _otsikkorivi(lehti) -> None:
    lehti.append([o for o, _ in SARAKKEET])
    for i, (_, leveys) in enumerate(SARAKKEET, start=1):
        solu = lehti.cell(row=lehti.max_row, column=i)
        solu.font = OTSIKKO_FONTTI
        solu.fill = OTSIKKO_TAUSTA
        solu.alignment = Alignment(vertical="center")
        lehti.column_dimensions[solu.column_letter].width = leveys


def luo() -> bytes:
    kirja = Workbook()
    lehti = kirja.active
    lehti.title = "Henkilöt"
    _otsikkorivi(lehti)
    lehti.freeze_panes = "A2"

    # Puhelin tekstiksi: muuten Excel tekee 0401234567:stä luvun 401234567.
    puhelin_sarake = next(i for i, (o, _) in enumerate(SARAKKEET, start=1) if o == "Puhelin")
    for rivi in range(2, TAYTETTAVIA_RIVEJA + 2):
        lehti.cell(row=rivi, column=puhelin_sarake).number_format = "@"

    # Tyypin pudotusvalikko. Ei estä muita arvoja (tuonti kertoo virheen riveittäin).
    tyyppi_sarake = lehti.cell(row=1, column=2).column_letter
    valinta = DataValidation(type="list", formula1='"cast,crew"', allow_blank=True, showErrorMessage=False)
    valinta.add(f"{tyyppi_sarake}2:{tyyppi_sarake}{TAYTETTAVIA_RIVEJA + 1}")
    lehti.add_data_validation(valinta)

    ohje = kirja.create_sheet("Ohje")
    ohje.column_dimensions["A"].width = 26
    for teksti in OHJE:
        ohje.append([teksti])
    ohje.cell(row=1, column=1).font = Font(bold=True)
    _otsikkorivi(ohje)
    for esimerkki in ESIMERKIT:
        ohje.append(esimerkki)

    KOHDE.parent.mkdir(parents=True, exist_ok=True)
    kirja.save(KOHDE)
    return KOHDE.read_bytes()


if __name__ == "__main__":
    data = luo()
    print(f"Kirjoitettu {KOHDE} ({len(data)} tavua)")

"""Luo Excel-tuonnin testitiedostot (ROADMAP O1) tähän hakemistoon.

    python tests/data/luo_tuontitiedostot.py

Tiedostot ovat versionhallinnassa, joten tätä tarvitsee ajaa vain, kun
esimerkkejä muutetaan.
"""

import io
import zipfile
from pathlib import Path

from openpyxl import Workbook

HAKEMISTO = Path(__file__).parent


def _tallenna(kirja: Workbook, nimi: str) -> bytes:
    puskuri = io.BytesIO()
    kirja.save(puskuri)
    data = puskuri.getvalue()
    (HAKEMISTO / nimi).write_bytes(data)
    return data


def henkilot_ok() -> bytes:
    kirja = Workbook()
    lehti = kirja.active
    lehti.title = "Henkilöt"
    lehti.append(["Tyyppi", "Nimi", "Rooli", "Titteli", "Puhelin", "Osoite", "Huomiot", "Allergiat"])
    lehti.append(["cast", "Aino Näyttelijä", "Liisa", None, "040 123 4567", "Mannerheimintie 1, Helsinki", None, "pähkinä"])
    lehti.append(["Työryhmä", "Bertta Valo", None, "Valomies", 401234567, "Hämeentie 5, Helsinki", "Oma auto usein", None])
    lehti.append([None, "Cecilia Rooliton", None, "Puvustaja", None, None, None, None])
    lehti.append([None, None, None, None, None, None, None, None])  # tyhjä rivi ohitetaan
    lehti.append([None, "Daniel Rooli", "Poliisi", None, None, "Kalevankatu 3, Helsinki", "=1+1", None])
    return _tallenna(kirja, "henkilot_ok.xlsx")


def henkilot_virheet() -> bytes:
    kirja = Workbook()
    lehti = kirja.active
    lehti.append(["Nimi", "Tyyppi", "Puhelin"])
    lehti.append(["Eero Kelpo", "crew", "050 1"])
    lehti.append(["Fanni Outo", "statisti", None])        # tuntematon tyyppi
    lehti.append([None, "cast", "050 2"])                 # nimi puuttuu
    lehti.append(["G" * 201, "crew", None])               # liian pitkä nimi
    lehti.append(["Hanna Puhelin", "crew", "1" * 51])     # liian pitkä puhelin
    return _tallenna(kirja, "henkilot_virheet.xlsx")


def puuttuva_sarake() -> bytes:
    kirja = Workbook()
    lehti = kirja.active
    lehti.append(["Etunimi", "Sukunimi", "Puhelin"])
    lehti.append(["Iida", "Ilman", "050 3"])
    return _tallenna(kirja, "puuttuva_sarake.xlsx")


def rikki(ok: bytes) -> None:
    # Katkaistu zip: alku on oikea xlsx, loppu (keskushakemisto) puuttuu.
    (HAKEMISTO / "rikki.xlsx").write_bytes(ok[: len(ok) // 2])


def ei_excel() -> None:
    # Tekstitiedosto .xlsx-päätteellä.
    (HAKEMISTO / "ei_excel.xlsx").write_bytes("nimi;puhelin\nJussi;050 4\n".encode())


def word_xlsx_paatteella() -> None:
    # Oikea zip ja [Content_Types].xml, mutta Word-asiakirja eikä taulukko.
    puskuri = io.BytesIO()
    with zipfile.ZipFile(puskuri, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/'
            'package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/'
            'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        )
        zf.writestr("word/document.xml", "<w:document/>")
    (HAKEMISTO / "word.xlsx").write_bytes(puskuri.getvalue())


def zip_pommi(ok: bytes) -> None:
    # Oikea xlsx, johon on lisätty 30 Mt nollia: pakattuna ~30 kt.
    puskuri = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(ok)) as lahde, zipfile.ZipFile(puskuri, "w", zipfile.ZIP_DEFLATED) as kohde:
        for osa in lahde.infolist():
            kohde.writestr(osa, lahde.read(osa))
        kohde.writestr("xl/media/pommi.bin", b"\0" * (30 * 1024 * 1024))
    (HAKEMISTO / "zip_pommi.xlsx").write_bytes(puskuri.getvalue())


if __name__ == "__main__":
    ok = henkilot_ok()
    henkilot_virheet()
    puuttuva_sarake()
    rikki(ok)
    ei_excel()
    word_xlsx_paatteella()
    zip_pommi(ok)
    for tiedosto in sorted(HAKEMISTO.glob("*.xlsx")):
        print(f"{tiedosto.name}: {tiedosto.stat().st_size} tavua")

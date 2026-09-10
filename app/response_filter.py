"""Roolipohjainen kenttäsuodatus API-vastauksiin (docs/tuotekartta.md,
vaihe D "Roolinäkyvyys"). EI TURVAOMINAISUUS - ks. app/rooli.py.

Piilotettavat-vakiot ovat kaikki tässä yhdessä paikassa (ei kunkin
routerin sisällä) - yksi tarkistettava lista siitä mitä KUSKI-rooli ei
näe koko API:ssa, helppo auditoida jatkossa.
"""

from pydantic import BaseModel
from fastapi.responses import JSONResponse

from app.models import KayttajaRooli

HENKILO_KUSKILTA_PIILOTETTAVAT = {"nouto_bufferi_min", "max_etuajassa_min"}
KUSKI_KUSKILTA_PIILOTETTAVAT = {"pickup_bufferi_min", "tuntihinta_eur"}
AJOLISTAVERSIO_KUSKILTA_PIILOTETTAVAT = {"kokonaiskustannus_eur"}
KEIKKA_KUSKILTA_PIILOTETTAVAT: set[str] = set()  # ei vielä mitään, mutta sama putki
OPTIMOINTIVASTAUS_KUSKILTA_PIILOTETTAVAT = {
    "kokonaiskustannus_eur": True,
    "kuskit": {"__all__": {"lisakustannus_eur"}},
    "skenaariot": True,
}


def _suodata(malli: BaseModel, rooli: KayttajaRooli, piilotettavat) -> dict:
    if rooli != KayttajaRooli.KUSKI:
        return malli.model_dump(mode="json")
    return malli.model_dump(mode="json", exclude=piilotettavat)


def json_vastaus(data, rooli: KayttajaRooli, piilotettavat, *, status_code: int = 200) -> JSONResponse:
    """data: yksi BaseModel TAI lista BaseModeleja."""
    if isinstance(data, list):
        sisalto = [_suodata(m, rooli, piilotettavat) for m in data]
    else:
        sisalto = _suodata(data, rooli, piilotettavat)
    return JSONResponse(sisalto, status_code=status_code)

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.services.osoite_ehdottaja import OsoiteEhdottaja, get_osoite_ehdottaja

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/osoitteet", tags=["osoitteet"])


class OsoiteEhdotus(BaseModel):
    nimi: str
    lat: float
    lon: float


@router.get("/ehdota", response_model=list[OsoiteEhdotus])
async def ehdota_osoitteita(
    q: str = Query(..., min_length=3, max_length=200, description="Hakuteksti, vähintään 3 merkkiä"),
    raja: int = Query(5, ge=1, le=10),
    ehdottaja: OsoiteEhdottaja = Depends(get_osoite_ehdottaja),
):
    """Osoite-ehdotukset osoitekentän automaattitäydennykseen. Valitun
    ehdotuksen lat/lon lähetetään tallennuksessa mukana, jolloin
    tallennus ei tarvitse erillistä geokoodausta."""
    try:
        ehdotukset = await ehdottaja.ehdota(q.strip(), raja)
    except httpx.HTTPError as e:
        logger.warning("Osoite-ehdotukset epäonnistuivat: %s", e)
        raise HTTPException(
            status_code=503, detail="Osoitehaku ei ole juuri nyt käytettävissä, kirjoita osoite käsin"
        )
    return [OsoiteEhdotus(nimi=e.nimi, lat=e.lat, lon=e.lon) for e in ehdotukset]

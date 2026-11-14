from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Kehityksen oletussalaisuus. Kelpaa VAIN kun AJURI_YMPARISTO=dev - muussa
# ympäristössä JWT_SECRET on pakko asettaa (ks. Settings._tarkista_jwt).
# Vähintään 32 tavua, koska HS256 vaatii sen (PyJWT varoittaa lyhyemmästä).
DEV_JWT_SECRET = "ajuri-dev-salaisuus-ei-tuotantoon-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://ajuri:ajuri@localhost:5432/ajuri"
    osrm_base_url: str = "https://router.project-osrm.org"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "Ajuri/1.0 (+https://github.com/Tinskutansku/Ajuri)"
    nominatim_countrycodes: str = ""  # tyhjä = ei maarajausta (oletus); esim. "fi" jos
                                       # tuotanto on varmasti vain kotimainen - kansain-
                                       # väliset yhteistuotannot tarvitsevat ulkomaisia
                                       # osoitteita, joten rajausta EI oleteta päälle
    geokoodaus_negatiivinen_ttl_pv: int = 7

    # Osoite-ehdotukset kirjoittaessa (app/services/osoite_ehdottaja.py).
    photon_base_url: str = "https://photon.komoot.io"
    # "lat,lon" johon tuloksia painotetaan (ei rajaa - ulkomaiset osoitteet
    # löytyvät yhä). Oletus Helsingin keskusta; tyhjä = ei painotusta.
    photon_bias: str = "60.1699,24.9384"

    # Kirjautuminen (app/auth.py). AJURI_YMPARISTO=dev sallii oletus-
    # salaisuuden; muuten puuttuva JWT_SECRET kaataa käynnistyksen.
    # Tiukemmat tuotantotarkistukset (pituus, tietokannan salasana jne.)
    # tulevat ROADMAPin kohdassa L1.
    ajuri_ymparisto: Literal["dev", "prod"] = "dev"
    jwt_secret: str | None = None
    jwt_voimassa_h: int = 12

    @model_validator(mode="after")
    def _tarkista_jwt(self) -> "Settings":
        if not self.jwt_secret:
            if self.ajuri_ymparisto != "dev":
                raise ValueError(
                    "JWT_SECRET puuttuu. Aseta ympäristömuuttuja JWT_SECRET "
                    "(esim. python -c \"import secrets; print(secrets.token_urlsafe(48))\") "
                    "tai kehityksessä AJURI_YMPARISTO=dev."
                )
            self.jwt_secret = DEV_JWT_SECRET
        return self


settings = Settings()

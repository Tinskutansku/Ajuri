from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Kehityksen oletussalaisuus. Kelpaa VAIN kun AJURI_YMPARISTO=dev - muussa
# ympäristössä JWT_SECRET on pakko asettaa (ks. Settings._tarkista_jwt).
# Vähintään 32 tavua, koska HS256 vaatii sen (PyJWT varoittaa lyhyemmästä).
DEV_JWT_SECRET = "ajuri-dev-salaisuus-ei-tuotantoon-0123456789abcdef"

# Prodissa JWT_SECRETin vähimmäispituus merkkeinä. HS256:n avaimen pitää
# olla vähintään 32 tavua; secrets.token_urlsafe(48) antaa 64 merkkiä.
JWT_SECRET_MIN_PITUUS = 32

# Tietokannan salasanat, joita ei hyväksytä prodissa (kehityksen oletukset).
HEIKOT_KANTASALASANAT = {"ajuri", "postgres", "password", "salasana"}


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
    # AJURI_YMPARISTO=prod lisää tuotantotarkistukset (_tarkista_prod).
    ajuri_ymparisto: Literal["dev", "prod"] = "dev"
    jwt_secret: str | None = None
    jwt_voimassa_h: int = 12

    # Pyyntörajoitukset (app/rajoitukset.py, ROADMAP L2). Muoto on
    # limits-kirjaston: "5/minute", "100/hour", "10/30 seconds".
    rajoitukset_kaytossa: bool = True
    rajoitus_kirjautuminen: str = "5/minute"       # IP-osoitetta kohden
    rajoitus_osoite_ehdotukset: str = "60/minute"  # käyttäjää kohden
    rajoitus_optimointi: str = "6/minute"          # käyttäjää kohden
    # Montako luotettua välityspalvelinta on backendin edessä. 0 = ei
    # yhtään, IP luetaan suoraan yhteydestä. Ks. asiakkaan_ip().
    luotetut_valityspalvelimet: int = Field(default=0, ge=0, le=5)

    @field_validator("database_url")
    @classmethod
    def _asyncpg_ajuri(cls, url: str) -> str:
        """Render (ja moni muu palvelu) antaa yhteysosoitteen muodossa
        `postgresql://...` tai `postgres://...`. Sovellus käyttää asyncpg-
        ajuria, joten skeema muutetaan muotoon `postgresql+asyncpg://`.
        Muut skeemat (esim. testien `sqlite+aiosqlite://`) pysyvät ennallaan."""
        for etuliite in ("postgresql://", "postgres://"):
            if url.startswith(etuliite):
                return "postgresql+asyncpg://" + url[len(etuliite):]
        return url

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

    @model_validator(mode="after")
    def _tarkista_prod(self) -> "Settings":
        """Prodissa käynnistys kaatuu selkeään virheeseen, jos asetukset
        ovat kehityksen oletuksia (ROADMAP L1). Kaikki virheet kerätään
        kerralla, jotta ne saa korjattua yhdellä kierroksella."""
        if self.ajuri_ymparisto != "prod":
            return self
        virheet: list[str] = []
        if self.jwt_secret and len(self.jwt_secret) < JWT_SECRET_MIN_PITUUS:
            virheet.append(
                f"JWT_SECRET on liian lyhyt ({len(self.jwt_secret)} merkkiä, vähintään "
                f"{JWT_SECRET_MIN_PITUUS}). Luo uusi: "
                "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if self.jwt_secret == DEV_JWT_SECRET:
            virheet.append("JWT_SECRET on kehityksen oletusavain. Luo oma avain tuotantoon.")
        salasana = urlsplit(self.database_url).password
        if not salasana or salasana.lower() in HEIKOT_KANTASALASANAT:
            virheet.append(
                "DATABASE_URL:n tietokantasalasana puuttuu tai on kehityksen oletus "
                "(esim. 'ajuri'). Aseta DATABASE_URL tuotantokannan omalla salasanalla."
            )
        if "cors_origins" not in self.model_fields_set:
            # Kehityksen localhost-oletukset eivät kuulu prodiin: ilman
            # CORS_ORIGINS-muuttujaa selain ei salli yhtään vierasta osoitetta.
            self.cors_origins = []
        if "*" in self.cors_origins:
            virheet.append(
                "CORS_ORIGINS ei saa sisältää '*' prodissa. Luettele frontin osoitteet, "
                'esim. CORS_ORIGINS=["https://ajuri.example"]'
            )
        if virheet:
            raise ValueError(
                "AJURI_YMPARISTO=prod, mutta asetuksissa on puutteita:\n- " + "\n- ".join(virheet)
            )
        return self

    @property
    def on_prod(self) -> bool:
        return self.ajuri_ymparisto == "prod"


settings = Settings()

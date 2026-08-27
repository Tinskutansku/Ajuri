# Ajuri — ajolistan hallinta

FastAPI-projektirunko kuvausten kuljetuslogistiikan hallintaan. Mukana on
perusdatan CRUD (tuotanto, henkilö, kuski, ajoneuvo, lokaatio) sekä
ajolistan optimointiservice (`docs/optimoija-spec.md`), joka ratkaisee
päivän kuljetustehtävät OR-Toolsilla ja tallentaa tuloksen versioituna.
Pohjana `ajolista_optimoija.py`-prototyyppi.

## Rakenne

```
app/
  main.py         FastAPI-sovellus ja reitittimien rekisteröinti
  models.py       SQLAlchemy 2.0 -mallit (ei muuteta ilman erillistä päätöstä)
  schemas.py      Pydantic v2 -skeemat (Create/Read per entiteetti + optimointi)
  database.py     Async-engine ja istunnot
  config.py       Asetukset (.env)
  routers/        CRUD-reitittimet + optimointi.py
  services/
    optimoija.py       OR-Tools-malli (pohja: ajolista_optimoija.py)
    kustannus.py        Kuskin päivän lisäkustannus sopimustyypin mukaan
    matka_cache.py       Ajoaikojen välimuisti (Matka-taulu)
    router_client.py     Reititys-API-abstraktio (OSRM julkinen demo)
  seed.py         Luo/päivittää realistisen demo-kuvauspäivän (python -m app.seed)
alembic/          Tietokantamigraatiot
tests/            Pytest-testit
frontend/         Vite + React -demofrontti (ks. frontend/README.md)
docs/optimoija-spec.md   Optimoijaservicen speksi
docs/tuotekartta.md      Jatkokehityksen vaiheet
ajolista_optimoija.py    Alkuperäinen OR-Tools-prototyyppi (viitteeksi)
```

## Käynnistys Docker Composella (suositeltu)

1. Kopioi `.env.example` -> `.env` ja muokkaa tarvittaessa.
2. Rakenna ja käynnistä:

   ```
   docker compose up --build
   ```

3. Aja migraatiot (ensimmäisellä kerralla, tai kun malleihin tulee muutoksia):

   ```
   docker compose exec app alembic upgrade head
   ```

4. API on osoitteessa http://localhost:8000, Swagger-UI http://localhost:8000/docs

Huom: Postgres on mäpätty isäntäkoneen porttiin **5433** (ei 5432), koska
koneella voi olla jo natiivi PostgreSQL-palvelu portissa 5432. Sovelluksen
sisäinen liikenne Docker-verkossa käyttää normaalia porttia 5432.

## Käynnistys paikallisesti ilman Dockeria

Vaatii käynnissä olevan PostgreSQL-tietokannan (esim. `docker compose up -d db`).

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# muokkaa DATABASE_URL osoittamaan tietokantaasi

alembic upgrade head
uvicorn app.main:app --reload
```

## Testit

```
pytest
```

Testit ajavat SQLite-muistikannalla, joten Postgresia ei tarvita testien
ajamiseen.

## Migraatiot

Ensimmäinen migraatio (`alembic/versions/..._init.py`) on generoitu
automaattisesti `app/models.py`:n perusteella. Mallien muuttuessa:

```
alembic revision --autogenerate -m "kuvaus muutoksesta"
alembic upgrade head
```

## Rajapinnat

CRUD-reitit perusdataentiteeteille:

- `/tuotannot`
- `/henkilot` (suodatus: `?tuotanto_id=`)
- `/kuskit` (suodatus: `?tuotanto_id=`)
- `/ajoneuvot` (suodatus: `?tuotanto_id=`)
- `/lokaatiot` (suodatus: `?tuotanto_id=`)

CRUD-reitit päiväkohtaiselle datalle:

- `/kuvauspaivat` (suodatus: `?tuotanto_id=`)
- `/paiva-lokaatiot` (suodatus: `?paiva_id=`)
- `/paiva-henkilot` (suodatus: `?paiva_id=`)
- `/paiva-kuskit` (suodatus: `?paiva_id=`)
- `/tehtavat` (suodatus: `?paiva_id=`)

Ajolistaversion/keikan toiminnot (ei omaa CRUD:ia — rivit syntyvät vain
optimoinnista):

- `POST /versiot/{versio_id}/julkaise` — asettaa version julkaistuksi ja
  poistaa julkaisun muilta saman päivän versioilta
- `PATCH /keikat/{keikka_id}/kuittaa` — merkitsee keikan ajetuksi
  (`kuitattu=true`), jota reoptimoinnin lukituslogiikka käyttää

Optimointi (`docs/optimoija-spec.md`):

- `POST /paivat/{paiva_id}/optimoi` — ratkaisee päivän kuljetustehtävät ja
  tallentaa tuloksen uutena `ajolista_versio`-versiona. Vaatii, että
  kuvauspäivän kaikilla tehtävillä ja tarjolla olevilla kuskeilla on
  koordinaatit tallennettuna (muuten `422`).

Reititys-API on OSRM:n julkinen demo-palvelin
(`https://router.project-osrm.org`, ks. `app/services/router_client.py`).
Se ei sovi tuotantokäyttöön (ei SLA:ta, rate limit) — vaihda
`OSRMRouterClient` toiseen `RouterClient`-toteutukseen tuotantoa varten.

## Demo-data

```
python -m app.seed
```

Luo (tai päivittää idempotentisti) yhden realistisen kuvauspäivän oikeilla
pääkaupunkiseudun koordinaateilla — ks. `docs/tuotekartta.md`.

## Frontend-demo

```
cd frontend
cp .env.example .env
npm install
npm run dev
```

Avaa http://localhost:5173. Vaatii backendin pyörimässä portissa 8000 —
CORS on sallittu porttiin 5173 (`app/config.py: cors_origins`). Ks.
`frontend/README.md`.

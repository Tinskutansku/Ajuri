# Ajuri — ajolistan hallinta

FastAPI-projektirunko kuvausten kuljetuslogistiikan hallintaan. Tässä
vaiheessa mukana on perusdatan CRUD (tuotanto, henkilö, kuski, ajoneuvo,
lokaatio). Ajolistan optimointi (`ajolista_optimoija.py`, OR-Tools) on
prototyyppi, joka sovitetaan myöhemmin `app/services`-kerrokseen — sitä
ei ole vielä kytketty API:in.

## Rakenne

```
app/
  main.py         FastAPI-sovellus ja reitittimien rekisteröinti
  models.py       SQLAlchemy 2.0 -mallit (ei muuteta ilman erillistä päätöstä)
  schemas.py      Pydantic v2 -skeemat (Create/Read per entiteetti)
  database.py     Async-engine ja istunnot
  config.py       Asetukset (.env)
  routers/        CRUD-reitittimet per entiteetti
  services/       Varattu tuleville palveluille (mm. optimoija)
alembic/          Tietokantamigraatiot
tests/            Pytest-testit
ajolista_optimoija.py   OR-Tools-prototyyppi (ei vielä kytketty)
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

## Rajapinnat (v1)

CRUD-reitit seuraaville perusdataentiteeteille:

- `/tuotannot`
- `/henkilot` (suodatus: `?tuotanto_id=`)
- `/kuskit` (suodatus: `?tuotanto_id=`)
- `/ajoneuvot` (suodatus: `?tuotanto_id=`)
- `/lokaatiot` (suodatus: `?tuotanto_id=`)

Päiväkohtainen data (kuvauspäivät, tehtävät, ajolistaversiot) ja
optimointi eivät ole vielä mukana.

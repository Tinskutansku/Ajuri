# AJURI — käynnistysmuistilappu

Kolme terminaalia. Kaikki komennot PowerShellissä.
Projektin juuri: `C:\Users\tanja\Source\repos\Ajuri`

---

## 0. Ennen kaikkea: Docker Desktop

1. Käynnistä **Docker Desktop** (Windowsin käynnistysvalikko)
2. Odota että se on valmis — ikoni lakkaa animoitumasta, sovellus sanoo
   "Engine running". Kestää helposti 1–2 min.
3. Varmista:
   ```
   docker ps
   ```
   Tyhjä taulukko otsikkoriveineen = valmis. Virhe = ei vielä.

---

## 1. Terminaali 1 — tietokanta + migraatiot

```
cd C:\Users\tanja\Source\repos\Ajuri
docker compose up -d db
venv\Scripts\activate
alembic upgrade head
```

Jos data on tyhjä tai haluat demopäivän:
```
python -m app.seed
```
(Idempotentti — voi ajaa uudestaan ilman duplikaatteja.)

Tämän terminaalin voi sen jälkeen jättää muuhun käyttöön (testit yms).

---

## 2. Terminaali 2 — backend

```
cd C:\Users\tanja\Source\repos\Ajuri
venv\Scripts\activate
uvicorn app.main:app --reload
```

Odota rivi `Application startup complete`. **Jätä pyörimään.**
Virheet näkyvät tässä terminaalissa — pidä näkyvissä kun testaat käsin.

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

---

## 3. Terminaali 3 — frontti

```
cd C:\Users\tanja\Source\repos\Ajuri\frontend
npm run dev
```

Avaa se osoite jonka Vite tulostaa (yleensä http://localhost:5173).
**Jätä pyörimään.**

⚠ Jos Vite sanoo "Port 5173 is in use, trying another one" → vanha
instanssi on jäänyt päälle. CORS on asetettu portille 5173, joten
muusta portista tulee "Failed to fetch". Korjaus: sulje vanhat
terminaalit tai tapa node-prosessit (ks. vianetsintä).

---

## Testit

```
cd C:\Users\tanja\Source\repos\Ajuri
venv\Scripts\activate
pytest
```
Kanta pitää olla käynnissä. Ajo kestää ~1 min (optimointitestit).

Yksi tiedosto:
```
pytest tests\test_geokoodaus.py -v
```

---

## Migraatiot

```
alembic upgrade head          # aja migraatiot
alembic check                 # onko malli ja migraatiot synkassa
alembic current               # missä versiossa ollaan
```

---

## Git

```
git status
git add .
git commit -m "viesti"
git push
```

---

## Vianetsintä

| Oire | Syy ja korjaus |
|---|---|
| `Connect call failed ... 5433` | Kanta ei pyöri → `docker compose up -d db` |
| `failed to connect to the docker API` | Docker Desktop ei ole käynnissä |
| `alembic`/`pytest` not recognized | venv ei aktiivinen → `venv\Scripts\activate` |
| `ModuleNotFoundError: No module named 'app'` | Olet väärässä kansiossa → backend ajetaan **juuresta**, ei frontendistä |
| Frontti: "Failed to fetch" | Backend ei pyöri, TAI Vite meni väärään porttiin (CORS) |
| `The token '&&' is not a valid statement separator` | PowerShell 5.1 ei tue `&&` → aja komennot erikseen tai käytä `;` |
| `curl -H` ei toimi | PowerShellin `curl` on eri komento → käytä `curl.exe` |

Node-prosessien tappo (jumittuneet Vite-instanssit):
```
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
```

Python-prosessien tappo (jumittunut uvicorn):
```
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## Demon ajaminen (esim. esittely)

1. Docker Desktop käyntiin, odota
2. Terminaali 1: `docker compose up -d db` → `venv\Scripts\activate` →
   `alembic upgrade head`
3. Terminaali 2: backend käyntiin
4. Terminaali 3: frontti käyntiin
5. Selain auki → valitse päivä → **★ Optimoi**

**Älä aja seediä uudestaan juuri ennen esittelyä**, jos data on jo
kunnossa — matka-välimuistissa olevat ajoajat tekevät optimoinnista
nopean ja verkosta riippumattoman.

Testaa kerran etukäteen ilman verkkoa: aja optimointi, katkaise wifi,
aja uudestaan. Jos menee läpi, välimuisti kattaa kaiken.

---

## Testidatan nyrkkisääntö

Manuaalitestit **omaan kertakäyttöiseen tuotantoon**, ei demo-seedin
tuotantoon (id 1). Silloin demo pysyy ehjänä vaikka jokin menisi pieleen.

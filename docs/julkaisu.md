# Julkaisu Renderiin (demo)

AJURI julkaistaan demoksi Renderin ilmaiselle tasolle `render.yaml`-
blueprintilla. Blueprint luo kolme osaa:

| Osa | Renderin tyyppi | Nimi |
|---|---|---|
| Backend (FastAPI, sama Dockerfile kuin paikallisesti) | Web Service, Docker, Free | `ajuri-api` |
| Frontend (Viten tuotantobuildi) | Static Site | `ajuri` |
| Tietokanta | Render Postgres 16, Free | `ajuri-kanta` |

Kaikki on Frankfurtissa (frontti tulee Renderin CDN:stä).

## Askeleet

### 1. Tili

1. Luo tili osoitteessa <https://render.com> (GitHub-kirjautuminen on helpoin).
2. Anna Renderille lukuoikeus `Tinskutansku/ajuri`-repoon, kun se kysyy.

### 2. Luo salaisuudet valmiiksi

Tarvitset kolme arvoa. Luo JWT-avain omalla koneella:

```
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

| Muuttuja | Palvelu | Arvo |
|---|---|---|
| `JWT_SECRET` | ajuri-api | yllä luotu avain (vähintään 32 merkkiä) |
| `NOMINATIM_USER_AGENT` | ajuri-api | esim. `Ajuri/1.0 (sinun@sahkoposti.fi)`. Nominatimin käyttöehdot vaativat yhteystiedon. |
| `CORS_ORIGINS` | ajuri-api | `["https://ajuri.onrender.com"]` (frontin osoite JSON-listana) |
| `VITE_API_BASE_URL` | ajuri | `https://ajuri-api.onrender.com` (ilman loppukauttaviivaa) |

Osoitteet `ajuri.onrender.com` ja `ajuri-api.onrender.com` toteutuvat vain,
jos nimet ovat vapaina. Muuten Render lisää nimeen loppuliitteen. Jos niin
käy, korjaa `CORS_ORIGINS` ja `VITE_API_BASE_URL` vaiheessa 4.

### 3. Blueprint

1. Renderin hallintapaneelissa **New → Blueprint**, valitse `ajuri`-repo ja
   haara `main`. Render löytää `render.yaml`-tiedoston itse.
2. Render kysyy `sync: false` -muuttujat (taulukko yllä). Liitä arvot.
   Render kysyy ne **vain tässä vaiheessa**. Myöhemmin niitä muutetaan
   palvelun *Environment*-välilehdeltä.
3. **Apply**. Ensimmäinen build kestää muutaman minuutin (OR-Tools on iso).

`DATABASE_URL` tulee tietokannasta automaattisesti. Render antaa sen muodossa
`postgresql://...`, ja sovellus vaihtaa sen itse asyncpg-muotoon.

### 4. Tarkista osoitteet

1. Avaa `ajuri-api`-palvelu. Osoite näkyy sivun yläreunassa. Kokeile
   `https://<osoite>/health`, vastauksen pitää olla `{"status":"ok"}`.
2. Avaa `ajuri`-sivu. Jos osoite poikkeaa vaiheen 2 arvauksesta, korjaa
   `CORS_ORIGINS` (ajuri-api) ja `VITE_API_BASE_URL` (ajuri). Frontti pitää
   buildata uudelleen (**Manual Deploy → Deploy latest commit**), koska Vite
   lukee osoitteen buildin aikana.

### 5. Demodata

Ilmaisella tasolla ei ole shelliä eikä kertaluonteisia ajoja, joten seed
ajetaan backendin käynnistyksen yhteydessä:

1. `ajuri-api` → *Environment* → `AJURI_SEED` = `true` → **Save**.
   Palvelu käynnistyy uudelleen ja ajaa `python -m app.seed` migraatioiden
   jälkeen.
2. Kirjaudu frontissa demokäyttäjällä (tunnukset README:n kohdassa
   "Käyttäjät ja kirjautuminen").

Seed on idempotentti. Kun `AJURI_SEED=true` on päällä, **jokainen
käynnistys palauttaa demopäivän seedin tilaan** ja demokäyttäjien salasanat
oletuksiin. Ilmaisella tasolla palvelu käynnistyy aina uniltaan, eli
demodata nollautuu käytännössä joka kerta, kun sovellus on ollut 15 min
käyttämättä. Demoon se sopii. Jos haluat muutosten säilyvän, aseta
`AJURI_SEED=false` seedin jälkeen.

**Huom:** demokäyttäjien salasanat ovat julkisia (README). Kuka tahansa,
joka tietää osoitteen, voi kirjautua demoon. Älä tallenna demoon oikeita
henkilötietoja.

### 6. Oma käyttäjä (valinnainen)

`python -m app.luo_kayttaja` vaatii shellin. Sen voi ajaa omalta koneelta
Renderin ulkoista yhteysosoitetta vasten: `ajuri-kanta` → *Connect* →
*External Database URL*. Lisää loppuun `?ssl=require`:

```
set DATABASE_URL=postgresql://ajuri:...@dpg-...frankfurt-postgres.render.com/ajuri?ssl=require
python -m app.luo_kayttaja --email ... --rooli tuotanto
```

Tämä on ainoa kohta, jossa kannan salasana käsitellään omalla koneella.
Tyhjennä muuttuja komennon jälkeen.

## Mitä julkaisussa tapahtuu

Backendin käynnistyskomento (`render.yaml`, `dockerCommand`):

1. `alembic upgrade head`. Jos migraatio epäonnistuu, uusi versio ei
   käynnisty ja Render pitää edellisen käynnissä.
2. Seed, jos `AJURI_SEED=true`
3. `uvicorn` Renderin antamaan porttiin (`PORT`)

Renderin terveystarkistus kutsuu `GET /health`, joka ei vaadi kirjautumista.

Uusi commit `main`iin julkaisee automaattisesti molemmat palvelut.

## Ilmaisen tason rajat

Tilanne 22.11.2026, ks. <https://render.com/docs/free>.

| Raja | Mitä se tarkoittaa AJURIlle |
|---|---|
| Backend nukahtaa 15 min käyttämättömänä, herääminen noin 1 min | Ensimmäinen pyyntö tauon jälkeen on hidas. Kirjautumissivu latautuu heti (CDN), mutta kirjautuminen odottaa backendin heräämistä. |
| 0,1 CPU ja 512 Mt muistia | Optimointi on selvästi hitaampi kuin omalla koneella. Aikaraja on enintään 60 s (L3), joten laskenta ei jää jumiin, mutta tulos voi olla heikompi kuin paikallisesti. |
| 750 instanssituntia / kk | Riittää yhdelle jatkuvasti päällä olevalle palvelulle. |
| Ei shelliä, ei pre-deploy-komentoa, ei ajastettuja ajoja | Siksi migraatiot ja seed ovat käynnistyskomennossa (ks. yllä). M2:n "yöllinen demodatan palautus" ei onnistu ilmaiseksi cron-jobina. |
| Tiedostojärjestelmä katoaa uudelleenkäynnistyksessä | AJURI ei tallenna tiedostoja levylle, joten ei vaikutusta. |
| **Postgres vanhenee 30 päivän päästä luonnista**, sitten 14 päivää aikaa ennen poistoa | Demokanta pitää luoda uudelleen kuukauden välein (tai siirtyä maksulliseen). Uusi kanta: poista vanha `ajuri-kanta`, synkronoi blueprint, aja seed. |
| Postgres 1 Gt, ei varmuuskopioita, yksi ilmainen kanta per tili | Demoon riittää. Älä pidä kannassa mitään, mitä ei voi luoda seedillä uudelleen. |

## Ulkoiset palvelut demossa

| Palvelu | Käyttö | Rajat |
|---|---|---|
| OSRM-demopalvelin (`router.project-osrm.org`) | ajoaikamatriisi optimoinnissa | Ei SLA:ta, tarkoitettu kokeiluun. Voi olla hidas tai pois päältä. Raskaaseen käyttöön oma reititinpalvelu. |
| Photon (`photon.komoot.io`) | osoite-ehdotukset kirjoittaessa | Reilun käytön periaate. AJURI rajaa 60 pyyntöön / min / käyttäjä (L2). |
| Nominatim (`nominatim.openstreetmap.org`) | osoitteen geokoodaus tallennettaessa | Enintään 1 pyyntö / s, yksilöivä User-Agent pakollinen, ei automaattitäydennystä. |

## Pyyntörajoitukset ja IP-osoite

Render ohjaa liikenteen välityspalvelimen kautta, joten yhteyden osoite on
Renderin eikä käyttäjän. `render.yaml` asettaa
`LUOTETUT_VALITYSPALVELIMET=1`, jolloin kirjautumisen rajoitus lukee
käyttäjän IP:n `X-Forwarded-For`-otsakkeen oikeanpuoleisimmasta arvosta.
Sitä asiakas ei voi väärentää (ks. `app/rajoitukset.py`).

Jos Render joskus lisää ketjuun useamman välityspalvelimen, kaikki
käyttäjät jakaisivat saman kirjautumiskiintiön (5 / min). Silloin oire on
turhat 429-vastaukset, ei rajoituksen ohittaminen. Korjaus on kasvattaa
lukua.

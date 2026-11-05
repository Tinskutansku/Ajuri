# ROADMAP — yöajojen tehtävälista

Claude ottaa ylimmän kohdan, jonka tila on `[ ]`. Tanja hyväksyy tämän
listan etukäteen. Järjestyksen tai sisällön muutos tehdään muokkaamalla
tätä tiedostoa. Tarkemmat taustat ovat `docs/tuotekartta.md`:ssä.

Tilat
- `[ ]` tekemättä
- `[PR #n]` PR auki, odottaa mergeä
- `[odottaa päätöstä #n]` poikkeama, ks. PR tai issue
- `[x]` mergetty

---

## Vaihe G — Pohjatiedot- ja Tehtävät-välilehdet

### G1 `[PR #2]` Pohjatiedot-välilehti luonnoksesta
Luonnos oli `docs/luonnokset/Pohjatiedot.jsx`, nyt `frontend/src/Pohjatiedot.jsx` (edellisen
istunnon suunnitelma, 961 riviä).
- Siirrä `frontend/src/Pohjatiedot.jsx`:ksi ja lisää välilehti `App.jsx`:n
  `TABS`-listaan Rekisterin ja Optimoinnin väliin
- Lisää `api.js`:ään luonnoksen tarvitsemat funktiot (kuvauspäivät
  tuotannolle, lokaatiot, ajoneuvot, `paiva_lokaatio`, `paiva_henkilo`,
  `paiva_kuski` CRUD). Endpointit ovat jo backendissä.
- Jos luonnos olettaa endpointin tai kentän, jota backendissä ei ole,
  se on poikkeama
- **Valmis kun:** `npm run lint` ja `npm run build` menevät läpi, ja
  PR:ssä on lista siitä mitä luonnokseen piti muuttaa ja miten
  välilehteä kokeillaan seed-datalla

### G2 `[ ]` Tehtävät-välilehti
- Päivän valinta, `POST /paivat/{id}/generoi-tehtavat` -nappi
- Generoidut ja käsin lisätyt erotettuina (badge riville)
- Tehtävän lisäys, muokkaus ja poisto käsin (lounashaku, kortit,
  lentokenttänouto)
- Generoinnin `varoitus`-kenttä näkyviin, jos päivällä on julkaistu versio
- **Valmis kun:** lint + build läpi, ja koko putki onnistuu selaimessa
  ilman Swaggeria (henkilöt → päivä → generoi → optimoi)

## Vaihe H — Osoitteen automaattitäydennys

### H1 `[ ]` Backend: osoite-ehdotukset
- `GeocoderClient`-rajapintaan metodi `ehdota(q, raja=5)`
- `GET /geokoodaa/ehdota?q=...` → lista `{nimi, lat, lon}`
- `FakeGeocoder` saa vastaavan metodin, testit ilman verkkoa
- Huom. tämä lisää abstraktiin rajapintaan metodin, mikä on
  esihyväksytty tässä kohdassa
- **Valmis kun:** testit endpointille (tulokset, tyhjä haku, liian
  lyhyt haku → 422)

### H2 `[ ]` Frontend: osoitekenttä ehdotuksilla
- Haku vasta ~500 ms kirjoitustauon ja vähintään 5 merkin jälkeen
  (Nominatimin 1 kutsu/s)
- Valinta täyttää osoitteen ja koordinaatit
- Käyttöön Rekisterissä (henkilöt, kuskit) ja Pohjatiedoissa (lokaatiot)
- **Valmis kun:** lint + build läpi, debounce näkyy koodissa selvästi

## Vaihe I — Tulostusversio ja "kuski pois pelistä"

### I1 `[ ]` Tulostusversio
- Ajolista ilman kustannuksia, yhteystiedot mukana, A4-tuloste
  (`window.print()`), muu UI piilotetaan `@media print`illä
- **Valmis kun:** lint + build läpi, tulosteessa ei näy yhtään
  euromäärää

### I2 `[ ]` "Kuski pois pelistä" -hätänappi
- `tarjolla=false` + reoptimointi `nyt`-hetkestä yhdellä painalluksella,
  ja paluu peliin samalla tavalla
- Jos backend tarvitsee uuden endpointin, tee se testeineen. Jos
  optimoijaan pitää koskea, se on poikkeama.
- **Valmis kun:** testi sille, että kuitatut keikat pysyvät lukittuina

## Vaihe J — Versiodiffi

### J1 `[ ]` Backend: kahden version vertailu
- `GET /versiot/{a}/diff/{b}` → siirtyneet ajat, kuskia vaihtaneet
  keikat, uudet, poistuneet
- Roolisuodatus: KUSKI ei näe kustannusmuutoksia
- **Valmis kun:** testit kaikille neljälle muutostyypille

### J2 `[ ]` Frontend: diffinäkymä
- Esim. "Näyttelijä 2: nouto 7:40 → 8:10 · Tiinalle +1 keikka"
- **Valmis kun:** lint + build läpi

## Pienet (voi tehdä kun iso kohta on odottamassa)

- `[PR #3]` Tietokantayhteyden virhe → 503 raa'an tracebackin sijaan (testi)
- `[PR #3]` `GET /` → tervetulovastaus 404:n sijaan (testi)
- `[PR #3]` pytest-asyncio-varoitus pois: `asyncio_default_fixture_loop_scope`
  `pytest.ini`:hin

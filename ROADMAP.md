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

### G1 `[x]` Pohjatiedot-välilehti luonnoksesta
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

### G2 `[x]` Tehtävät-välilehti
- Päivän valinta, `POST /paivat/{id}/generoi-tehtavat` -nappi
- Generoidut ja käsin lisätyt erotettuina (badge riville)
- Tehtävän lisäys, muokkaus ja poisto käsin (lounashaku, kortit,
  lentokenttänouto)
- Generoinnin `varoitus`-kenttä näkyviin, jos päivällä on julkaistu versio
- **Valmis kun:** lint + build läpi, ja koko putki onnistuu selaimessa
  ilman Swaggeria (henkilöt → päivä → generoi → optimoi)

## Vaihe H — Osoitteen automaattitäydennys

### H1+H2 `[x]` Osoite-ehdotukset kirjoittaessa
Tehty yhdessä PR:ssä Tanjan ollessa paikalla 6.11. Nominatimin käyttöehdot
kieltävät automaattitäydennyksen, joten Tanja valitsi Photonin
(`app/services/osoite_ehdottaja.py`, oma `OsoiteEhdottaja`-abstraktio).
- `GET /osoitteet/ehdota?q=...` → lista `{nimi, lat, lon}`
- `frontend/src/OsoiteKentta.jsx` käytössä Rekisterissä (henkilöt, kuskit)
  ja Pohjatiedoissa (uusi lokaatio)
- Jatkossa: Tehtävät-välilehden vapaa osoite (G2, PR #6) samaan kenttään

## Vaihe I — Tulostusversio ja "kuski pois pelistä"

### I1 `[x]` Tulostusversio
- Ajolista ilman kustannuksia, yhteystiedot mukana, A4-tuloste
  (`window.print()`), muu UI piilotetaan `@media print`illä
- **Valmis kun:** lint + build läpi, tulosteessa ei näy yhtään
  euromäärää

### I2 `[PR #16]` "Kuski pois pelistä" -hätänappi
- `tarjolla=false` + reoptimointi `nyt`-hetkestä yhdellä painalluksella,
  ja paluu peliin samalla tavalla
- Jos backend tarvitsee uuden endpointin, tee se testeineen. Jos
  optimoijaan pitää koskea, se on poikkeama.
- **Valmis kun:** testi sille, että kuitatut keikat pysyvät lukittuina
- Tanjan päätös (PR #16): reoptimoinnissa mitään ei sijoiteta menneisyyteen,
  eli kenenkään kuskin reitti ei ala ennen `nyt`-hetkeä

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

- `[x]` Tietokantayhteyden virhe → 503 raa'an tracebackin sijaan (testi)
- `[x]` `GET /` → tervetulovastaus 404:n sijaan (testi)
- `[x]` pytest-asyncio-varoitus pois: `asyncio_default_fixture_loop_scope`
  `pytest.ini`:hin
- `[ ]` **Näkyvät kenttäotsikot Rekisteriin (saavutettavuus, Tanjan toive 6.11.)**
  Nyt kenttien nimi näkyy vain haaleana placeholderina, joka katoaa kun
  kenttään kirjoittaa. Placeholder ei kelpaa otsikoksi (WCAG 3.3.2 ja 1.3.1).
  - Näyttelijät- ja Työryhmä-korttiin otsikkorivi kenttien yläpuolelle:
    Nimi, Roolinimi / Titteli, Osoite, Puhelin. Kuskit-korttiin vastaavasti:
    Nimi, Puhelin, Sopimus, €/h, Kotiosoite, Pickup-bufferi.
  - Jokainen kenttä kytketään otsikkoonsa ruudunlukijaa varten
    (`<label htmlFor>` + `id` tai `aria-label`). `Kentta` ja `OsoiteKentta`
    saavat tähän valinnaisen `id`/`label`-propin.
  - Kapealla näytöllä, kun rivi rivittyy, otsikko kulkee kentän mukana
    (otsikko kentän yläpuolella per kenttä, ei erillinen taulukkorivi).
  - Pidä `pikkuLabel`-tyyli, jota Pohjatiedot jo käyttää (NIMI, OSOITE).
  - **Valmis kun:** lint + build läpi, ja PR:ssä on kuvakaappaus
    Rekisteristä sekä leveänä että mobiilileveydellä
- `[ ]` **Optimointi-välilehti muistaa tuloksen (Tanjan toive 6.11.)**
  Nyt sivun päivitys kesken laskennan hukkaa tuloksen näkyvistä, vaikka
  optimointi valmistuu backendissä ja tallentuu uudeksi ajolistaversioksi.
  - Kun päivä valitaan, näytä sen viimeisin tallennettu ajolista heti
    (olemassa olevat versio-endpointit, ks. `app/routers/versiot.py`)
  - Jos päivälle on optimointi kesken (`app/services/laskenta.py`:n
    `paivan_lukko`), näytä "Laskenta käynnissä…" ja hae tulos, kun se valmistuu
    (esim. kevyt tilaendpoint `GET /paivat/{id}/optimointi` + kysely 3 s välein)
  - Roolisuodatus pysyy samana kuin optimointivastauksessa (KUSKI ei näe
    kustannuksia). Jos tämä vaatii muutoksia `response_filter.py`:hin, se on poikkeama.
  - **Valmis kun:** testi tilaendpointille (käynnissä / ei käynnissä), lint +
    build läpi, ja PR:ssä ohje: Optimoi → päivitä sivu → tulos ilmestyy
- `[ ]` **Seed: noudot ja paluut generoiduiksi**
  `app/seed.py` luo seed-päivän noudot ja paluut käsin lisättyinä
  (`generoitu=false`), joten "Generoi tehtävät" lisää ne toiseen kertaan.
  Tuplat jäävät sijoittamatta ja hidastavat optimointia (30 sijoittamatonta 6.11.).
  - Merkitse seedin generoinnin kaltaiset tehtävät `generoitu=true`.
    Erikoistehtävät (esim. lounashaku, lentokenttä) jäävät käsin lisätyiksi.
  - Seed on idempotentti, eli olemassa olevalle kannalle ajettuna se ei saa
    luoda tuplia. Kerro PR:ssä, korjaako uudelleenajo vanhan kannan vai
    tarvitaanko tyhjä kanta.
  - **Valmis kun:** testi, jossa seed + generointi ei tuota tuplanoutoja

# AJURI — Tuotekartta

Tilanne: FastAPI-runko + perusdata-CRUD + päiväkohtainen CRUD +
optimoijaservice (OR-Tools, OSRM, matka-välimuisti, reoptimointi,
syyanalyysi, skenaariot) + tehtävägenerointi + soft delete (tehtävät sekä
henkilöt/kuskit/lokaatiot, käyttötietoendpointein) + versioiden
värikoodaus + bufferit + roolinäkyvyys + geokoodaus valmiina ja
testattuna (vaiheet A–F). Lisäksi `app/seed.py` — idempotentti
seed-skripti joka luo realistisen demo-kuvauspäivän oikeilla
pääkaupunkiseudun koordinaateilla, ainoa tapa saada dataa softaan ilman
käsityötä — ja `frontend/`-hakemistossa Vite + React -frontti, jossa on
neljä välilehteä: **Rekisteri** (henkilöiden ja kuskien CRUD,
poistodialogi näyttää käyttövaroituksen), **Pohjatiedot** (kuvauspäivän
kokoaminen), **Tehtävät** (generointi ja käsin lisätyt erikoiskeikat) ja
**Optimointi** (valitse päivä, optimoi, katso tulos per kuski).

Backend on kokonaisuudessaan tehty. Jäljellä oleva työ (vaiheet G–J) on
käyttöliittymää.

---

## Vaihe A — Päiväkohtainen CRUD (valmis)

Ilman näitä mikään muu ei etene: optimoijaa ei voi käyttää ilman että päivän
datan saa sisään API:sta.

- REST-endpointit: `kuvauspaiva`, `paiva_lokaatio`, `paiva_henkilo`,
  `paiva_kuski`, `tehtava` — sama kaava kuin perusdata-CRUD:ssa
- Version julkaisu: `POST /versiot/{id}/julkaise` (asettaa `julkaistu=true`,
  poistaa julkaisun muilta saman päivän versioilta)
- Pieni mutta tärkeä: `PATCH /keikat/{id}/kuittaa` (`kuitattu=true`) —
  reoptimoinnin lukituslogiikka tarvitsee tämän ollakseen käyttökelpoinen

## Vaihe B — Tehtävägenerointi (valmis)

Vaihe 1 → 2 -logiikka:
- Nouto ennen callia (oma call tai yleinen) → siirtymä → paluu wrapissa
- Poikkeusliput per henkilö: oma_auto, ei_paluuta, siirtyy
- `paiva_henkilo.siirtyma_klo`: henkilökohtainen siirtymäaika, joka ohittaa
  lokaation yleisen ajan (kaikki eivät siirry samaan aikaan)
- Generoidut rivit `generoitu=true`; uudelleengenerointi korvaa VAIN omat
  rivinsä, ei koskaan käsin lisättyjä — soft delete (vaihe B2) pitää tämän
  turvallisena vaikka päivälle olisi jo optimoitu ajolista
- Jos päivällä on julkaistu ajolistaversio, generointi silti onnistuu —
  vastauksessa `varoitus`-kenttä muistuttaa ajamaan optimoinnin uudelleen,
  koska julkaistu versio ei automaattisesti sisällä juuri generoituja
  tehtäviä
- Endpoint: `POST /paivat/{id}/generoi-tehtavat` →
  `{"tehtavat": [...], "varoitus": string | null}`

## Vaihe B2 — Tehtävien soft delete + versioiden värikoodaus (valmis)

Ongelma: kun call sheet muuttuu ja tehtävät generoidaan uudelleen, vanhoja
tehtäviä ei voi poistaa — niihin viittaa aiempien ajolistaversioiden keikkoja,
ja vanhat versiot on nimenomaan säilytettävä (pitää voida tarkistaa jälkikäteen
minkä listan mukaan mentiin).

**Soft delete:**
- `tehtava.aktiivinen: bool = True` + migraatio
- Uudelleengenerointi ei poista rivejä vaan merkitsee vanhat generoidut
  passiivisiksi ja luo uudet; `DELETE /tehtavat/{id}` (myös käsin luodut)
  toimii samoin
- `GET /tehtavat` ja `GET /tehtavat/{id}` piilottavat passiiviset oletuksena;
  `sisalla_passiiviset=true` näyttää myös ne (historiakatselu)
- Optimointi käyttää vain aktiivisia tehtäviä — lukitun (kuitatun) keikan
  tehtävä näytetään silti oikein vaikka se olisi sittemmin passivoitu
- Vanhat versiot säilyvät ehjinä, FK-ongelma katosi kokonaan — vaiheen B
  väliaikainen 409-esto poistui tarpeettomana

**Versioiden värikoodaus:**
- `ajolista_versio.tunniste`: WHITE, BLUE, PINK, YELLOW, kiertyy numeroituna
  ("2. WHITE"…) neljännen jälkeen, oma kierto per päivä
- Seuraava väri annetaan automaattisesti kun versio julkaistaan;
  jo väritetty versio ei väritetä uudelleen
- Blue call sheet → blue ajolista: dokumentit puhuvat samaa kieltä, ja
  "minkä listan mukaan mennään" on yksiselitteinen kysymys

## Vaihe C — V1.1 Bufferit ja henkilökohtaiset aikapreferenssit (spec §8, valmis)

Yksi migraatio, kolme kenttää — kaikki samaa perhettä (henkilö- ja
kuskikohtaisia aikasäätöjä optimoinnin oletusten päälle):

- `kuski.pickup_bufferi_min` — kuskikohtainen palveluaika (noudot kestävät
  kauemmin joillakin)
- `henkilo.nouto_bufferi_min` — henkilökohtainen palveluaika (tyypillisesti
  myöhässä noudosta)
- `henkilo.max_etuajassa_min` — kuinka paljon ennen call timea henkilö
  suostuu olemaan perillä; ohittaa globaalin 30 min oletuksen. Generointi
  laskee tästä `perilla_aikaisintaan` (0-240 min validoitu Pydantic-tasolla).

Optimoijamuutos: ajoneuvokohtaiset transit-callbackit (`AddDimensionWithVehicleTransits`)
lisäävät noutosolmun kestoon molemmat bufferit **vain aikadimensioon, ei
kaarikustannukseen** — kustannusevaluaattori pysyy bufferittomana, jotta
optimoija ei systemaattisesti välttäisi kuskia jolla on realistinen bufferi.

**Näkyvyys toteutettu vaiheessa D** ("Roolinäkyvyys") roolipohjaisella
API-suodatuksella, samalla mekanismilla kuin kustannuskentät.

## Vaihe D — Roolinäkyvyys ja Rekisteri-välilehti (valmis)

**Roolinäkyvyys API-tasolla:** `app/rooli.py` (roolin lähde, toistaiseksi
`X-Rooli`-header, oletus TUOTANTO — EI turvaominaisuus, ks. README) +
`app/response_filter.py` (kenttäsuodatus, yksi paikka jossa määritellään
mitä KUSKI-rooli ei näe). KUSKI-roolilta pois kaikista vastauksista
(kenttä puuttuu kokonaan, ei vain `null`):
- kustannuskentät: `ajolista_versio.kokonaiskustannus_eur`,
  kuskikohtainen `lisakustannus_eur`, koko skenaariovertailu
- vaihe C:n henkilökohtaiset kentät: `henkilo.nouto_bufferi_min`,
  `henkilo.max_etuajassa_min`, `kuski.pickup_bufferi_min`,
  `kuski.tuntihinta_eur`
- Samalla lisätty puuttuneet luku-endpointit joita kuskin ajolistanäkymä
  tarvitsee (niitä ei ollut ollenkaan aiemmin — vain `/optimoi`, joka
  laskee UUDEN version joka kutsulla): `GET /versiot?paiva_id=&julkaistu=`,
  `GET /versiot/{id}`, `GET /keikat?versio_id=`

**Rekisteri-välilehti frontissa:** henkilöiden (näyttelijät/työryhmä) ja
kuskien CRUD ilman Swaggeria. `App.jsx` on ohut kuori välilehtinavigaatiolla,
`Rekisteri.jsx` ja `Optimointi.jsx` omina komponentteinaan. Inline-editointi:
tekstikentät tallentuvat blur:issa vain jos arvo muuttui, valinnat ja ruksit
heti. "+ Lisää" luo rivin paikallisesti ja lähettää POST:in vasta kun nimi on
annettu (ei roskarivejä vahinkoklikkauksista). "ei koordinaatteja" -merkki
riveillä joilta geokoodaus puuttuu.

## Vaihe E — Geokoodaus (valmis)

- Osoite → lat/lon tallennusvaiheessa (`POST`/`PUT` henkilo, lokaatio,
  kuski) `GeocoderClient`-abstraktion takana (`app/services/geocoder_client.py`,
  sama kuvio kuin `RouterClient`), toteutus `NominatimGeocoder` — yksilöivä
  User-Agent ja 1 kutsu/s -rajoite Nominatimin käyttöehtojen mukaisesti
  (`nominatim_countrycodes`-asetus oletuksena tyhjä, koska tuotannot voivat
  olla kansainvälisiä yhteistuotantoja)
- Poistaa käsin syötettävät koordinaatit — Excel-tuonti muuttuu oikeasti
  käyttökelpoiseksi
- Välimuisti kantaan (`geokoodi`-taulu, `app/services/geokoodaus_cache.py`):
  sama osoite (normalisoituna) kysytään ulkoiselta palvelulta vain kerran;
  epäonnistunutkin haku muistetaan `settings.geokoodaus_negatiivinen_ttl_pv`
  (oletus 7 vrk) ajaksi, jotta pysyvästi toimimaton osoite ei jää ikuisesti
  jumiin mutta ei myöskään tuki uudelleenyrityksiä
- Geokoodauksen epäonnistuminen (verkkovirhe tai "ei löytynyt") ei koskaan
  estä henkilön/lokaation/kuskin tallennusta — koordinaatit jäävät tyhjiksi,
  virhe lokiin
- `POST /tuotannot/{id}/geokoodaa` täydentää kaikki koordinaatittomat rivit
  kerralla (Excel-tuonnin jälkeen), eräkoolla (`raja`, oletus 15 — Nominatimin
  1 kutsu/s tarkoittaisi muuten yli minuutin auki olevaa HTTP-pyyntöä) ja
  `jaljella`-laskurilla ohjaamaan seuraavaa kutsua

---

## Vaihe F — Soft delete perusdatalle + käyttötieto (valmis)

**Ongelma:** `DELETE /kuskit/{id}` (samoin henkilöt ja lokaatiot) kaatuu
tällä hetkellä 500:aan `IntegrityError`-virheeseen, jos riviin viittaa
`paiva_kuski`/`paiva_henkilo`/`paiva_lokaatio`-rivejä. Tietokanta toimii
oikein — se estää historian rikkomisen — mutta käyttäjä ei saa tietää
mitään, ja kovan poiston salliminen muuttaisi vanhoja ajolistoja
jälkikäteen.

Sama ratkaisu kuin tehtäville vaiheessa B2, nyt perusdatalle. Sen jälkeen
kaikilla resursseilla on sama poistosemantiikka, mikä on helpompi selittää
kuin "tehtävät soft, muut hard".

- `henkilo.aktiivinen`, `kuski.aktiivinen`, `lokaatio.aktiivinen`
  (bool, oletus True) + migraatio
- `DELETE` merkitsee passiiviseksi; ulkoinen käytös ennallaan
  (sama statuskoodi, rivi katoaa listauksista)
- `GET`-listaukset piilottavat passiiviset oletuksena;
  `sisalla_passiiviset=true` näyttää myös ne
- `GET /{resurssi}/{id}/kaytto` → missä kuvauspäivissä rivi on mukana
  (päivän id, pvm, paiva_nro) — frontin varoitusdialogia varten
- Optimointi ja generointi käyttävät vain aktiivisia rivejä
- Frontin poistodialogi: jos rivi on käytössä, näytä konkreettinen
  varoitus ennen vahvistusta:
  > "Kuski on mukana 3 kuvauspäivässä (22/49, 23/49, 24/49). Poistaminen
  > piilottaa hänet listoilta, mutta vanhat ajolistat säilyvät ennallaan.
  > Poistetaanko?"
- Lisäksi: `paiva_henkilo`/`paiva_kuski`/`paiva_lokaatio`-routerit (POST/PUT)
  estävät passiivisen henkilön/kuskin/lokaation liittämisen kuvauspäivään
  (422) — muuten API sallisi hiljaisen ristiriidan jota olisi vaikea
  jäljittää (poistettu rivi katoaisi optimoinnista/generoinnista selittämättä)

## Vaihe G — Pohjatiedot- ja Tehtävät-välilehdet (valmis)

Tämän jälkeen koko putki toimii ilman Swaggeria: henkilöt sisään →
päivä kasaan → generoi → optimoi → ajolista ulos.

**Pohjatiedot:**
- Kuvauspäivän valinta ja luonti (call, lounas, wrap, päivä nro)
- Päivän lokaatiot järjestyksineen ja siirtymäaikoineen
- Ketkä ovat mukana (`paiva_henkilo`): oma call, oma_auto, ei_paluuta,
  siirtyy, henkilökohtainen `siirtyma_klo`
- Ketkä kuskit tarjolla (`paiva_kuski`) ja millä autolla

**Tehtävät:**
- `POST /paivat/{id}/generoi-tehtavat` -nappi; generoitu lista näkyviin
- Generoidut ja käsin lisätyt erotettuina (merkintä riville)
- Tehtävien muokkaus, poisto ja lisäys käsin (erikoiskeikat: lounashaku,
  kortit, lentokenttänouto)
- Generoinnin `varoitus`-kenttä näkyviin, jos päivällä on julkaistu versio

## Vaihe H — Osoitteen automaattitäydennys

Nyt osoitteen voi kirjoittaa väärin eikä käyttäjä näe mihin se osui —
"Humalistonkatu 1" voi olla Turussa tai Helsingissä, ja ainoa palaute on
"ei koordinaatteja" -merkki joka kertoo vain onnistuiko haku, ei osuiko
se oikeaan paikkaan.

- `GeocoderClient`-rajapintaan uusi metodi: ehdotukset (esim. 5 kpl),
  ei vain paras osuma
- `GET /geokoodaa/ehdota?q=...` → lista ehdotuksia nimineen ja
  koordinaatteineen
- Frontissa osoitekenttä ehdottaa kirjoittaessa; valinta täyttää sekä
  osoitteen että koordinaatit
- **Nominatimin 1 kutsu/s:** haku vasta ~500 ms kirjoitustauon jälkeen
  ja vähintään ~5 merkin jälkeen — muuten käyttöehdot rikkoutuvat heti
- Käytössä sekä Rekisterissä (henkilöt, kuskit) että Pohjatiedoissa
  (lokaatiot), siksi tehdään vasta vaiheen G jälkeen

## Vaihe I — Tulostusversio ja "kuski pois pelistä"

Molemmat pieniä, molemmat tarvitaan heti oikeassa käytössä.

- **Tulostusversio:** ajolista ilman kustannuksia, yhteystiedot mukana,
  A4-henkinen tuloste (`window.print()`), muu UI piilotetaan printistä.
  Runnerille ei kuulu se mikä maksaa mitäkin.
- **"Kuski pois pelistä" -hätänappi:** `tarjolla=false` + reoptimointi
  `nyt`-hetkestä yhdellä painalluksella. Se 6:05-paniikkipolku: auto ei
  käynnisty, kuski pois, uusi ajolista minuutissa. Kun korvaava auto
  löytyy, kuski takaisin peliin ja uusi optimointi.

## Vaihe J — Versiodiffi

Draft call sheet → final -työnkulun ydin: kun uusi versio syntyy, mitä
muuttui edelliseen nähden. Ilman tätä koordi joutuu vertailemaan kahta
listaa rivi riviltä juuri silloin kun on eniten kiire.

- Kahden version vertailu: kenen ajat siirtyivät, mitkä keikat vaihtoivat
  kuskia, mikä on uutta, mikä poistui
- Esim. "Näyttelijä 2: nouto 7:40 → 8:10 · Tiinalle +1 keikka · muut ennallaan"
- Visuaalisesti hankalin osa, tehdään viimeisenä kun muu on paikallaan

---

## V2 — arvojärjestyksessä

1. **Kuskin mobiilinäkymä + statusviestintä** (spec §9) — "Kyydissä"/"Perillä"
   -napit, automaattiviestit (maskille saapumisarvio), muistutukset, offline-jono.
   Suurin päivittäinen ajansäästö optimoinnin jälkeen.
2. **Excel-tuonti** rekisteriin — nimi, titteli/rooli, osoite, puhelin;
   koordinaatit hoituvat geokoodauksella (vaihe E), joten tuonti on nyt
   oikeasti käyttökelpoinen
3. **Taksi-fallback** — sijoittamaton keikka → "merkitse taksille", näkyy
   ajolistassa TAKSI-rivinä + kustannusarvio
4. **Työvuororaportti** — kuskien vuorot + viikkosaldo (37,5 h/vko) exportina
   TP:n tarkistukseen ja vuoroilmoituksiin
5. **Korjausehdotukset sijoittamattomille** ("ota Kalle käyttöön, +88 €") —
   skenaariomoottori on jo olemassa, tämä on sen paketointia
6. Käyttäjähallinta + autentikointi (roolit oikeasti voimaan — `X-Rooli`
   on väliaikainen eikä turvaominaisuus)
7. Itseoppivat bufferit toteumadatasta
8. Max-paikat hyväksynnällä, shuttle-ikkunat, viikkosaldo optimointirajoitteena,
   asynkroninen optimointi, osastoautot hätävarana
9. Tuotantoreititin (oma OSRM-instanssi tai ORS-avain) — RouterClient valmiina
10. **"Julkaistu versio vanhentunut" -tila yleisemmin** — nyt varoitus tulee
    vain `generoi-tehtavat`-kutsusta (vaihe B), mutta sama pätee kun
    tehtäviä muokataan käsin tai kuskeja otetaan pois tarjolta julkaisun
    jälkeen. Aikaleimavertailu (onko päivän data muuttunut version luonnin
    jälkeen) ratkaisisi tämän kerralla kaikille muutostavoille erillisten
    kohdennettujen varoitusten sijaan.
11. Pieniä: tietokantayhteyden virhe → 503 raakan tracebackin sijaan,
    `GET /` → tervetulovastaus 404:n sijaan

## Pitchi (kun tätä esitellään alan ihmisille)

"Ajolistan tekeminen on hidasta — mutta pahinta on että se ei koskaan pysy
tehtynä." Demo: Excel sisään → arvio minuutissa → muutos → uusi versio + diffi
minuutissa.

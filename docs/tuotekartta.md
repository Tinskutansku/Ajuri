# AJURI — Tuotekartta

Tilanne: FastAPI-runko + perusdata-CRUD + optimoijaservice (OR-Tools, OSRM,
matka-välimuisti, reoptimointi, syyanalyysi, skenaariot) valmiina ja testattuna.
Tämä dokumentti kertoo missä järjestyksessä loput rakennetaan ja miksi.

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

## Vaihe B — Tehtävägenerointi

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

## Vaihe C — V1.1 Bufferit ja henkilökohtaiset aikapreferenssit (spec §8)

Yksi migraatio, kolme kenttää — kaikki samaa perhettä (henkilö- ja
kuskikohtaisia aikasäätöjä optimoinnin oletusten päälle):

- `kuski.pickup_bufferi_min` — kuskikohtainen palveluaika (noudot kestävät
  kauemmin joillakin)
- `henkilo.nouto_bufferi_min` — henkilökohtainen palveluaika (tyypillisesti
  myöhässä noudosta)
- `henkilo.max_etuajassa_min` — kuinka paljon ennen call timea henkilö
  suostuu olemaan perillä; ohittaa globaalin 30 min oletuksen. Generointi
  laskee tästä `perilla_aikaisintaan`.

Optimoijamuutos: transit-callback lisää noutosolmun kestoon molemmat bufferit.
Näkyvyys: henkilökohtaiset kentät vain TUOTANTO/KOORDI (syy voi olla arkaluontoinen)
— ei tulosteisiin eikä kuskien näkymiin.

## Vaihe D — React-frontti

Käyttöliittymäluonnos toimii speksinä:
- Välilehdet: Rekisteri (+ Excel-tuonti) · Pohjatiedot · Tehtävät · Ajolista
- Ajolistassa: Suunnittelu (€, aikajanat, skenaariot) + Tulostusversio (ei €)
- Uutta luonnoksen päälle:
  - **"Kuski pois pelistä"** -hätänappi: tarjolla=false + reoptimointi nyt-hetkestä
    yhdellä painalluksella (se 6:05-paniikkipolku)
  - **Versiodiffi**: uusi versio vs edellinen — mikä muuttui, kenen ajat siirtyivät
    (draft call sheet → final -työnkulun ydin)
  - Sijoittamattomat syineen näkyvästi esiin
- Roolinäkyvyys: kustannuskentät pois KUSKI-roolilta jo API-tasolla

## Vaihe E — Geokoodaus

- Osoite → lat/lon tallennusvaiheessa (henkilo, lokaatio, kuski)
- Lähde: esim. Nominatim (ilmainen, riittää) `GeocoderClient`-abstraktion taakse
- Poistaa käsin syötettävät koordinaatit — Excel-tuonti muuttuu oikeasti
  käyttökelpoiseksi

---

## V2 — arvojärjestyksessä

1. **Kuskin mobiilinäkymä + statusviestintä** (spec §9) — "Kyydissä"/"Perillä"
   -napit, automaattiviestit (maskille saapumisarvio), muistutukset, offline-jono.
   Suurin päivittäinen ajansäästö optimoinnin jälkeen.
2. **Taksi-fallback** — sijoittamaton keikka → "merkitse taksille", näkyy
   ajolistassa TAKSI-rivinä + kustannusarvio
3. **Työvuororaportti** — kuskien vuorot + viikkosaldo (37,5 h/vko) exportina
   TP:n tarkistukseen ja vuoroilmoituksiin
4. **Korjausehdotukset sijoittamattomille** ("ota Kalle käyttöön, +88 €") —
   skenaariomoottori on jo olemassa, tämä on sen paketointia
5. Käyttäjähallinta + autentikointi (roolit oikeasti voimaan)
6. Itseoppivat bufferit toteumadatasta
7. Max-paikat hyväksynnällä, shuttle-ikkunat, viikkosaldo optimointirajoitteena,
   asynkroninen optimointi, osastoautot hätävarana
8. Tuotantoreititin (oma OSRM-instanssi tai ORS-avain) — RouterClient valmiina

## Pitchi (kun tätä esitellään alan ihmisille)

"Ajolistan tekeminen on hidasta — mutta pahinta on että se ei koskaan pysy
tehtynä." Demo: Excel sisään → arvio minuutissa → muutos → uusi versio + diffi
minuutissa.

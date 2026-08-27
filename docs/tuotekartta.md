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

Ei uutta migraatiota — kaikki taulut olivat jo ensimmäisessä migraatiossa.

## Vaihe B — Tehtävägenerointi

Vaihe 1 → 2 -logiikka:
- Nouto ennen callia (oma call tai yleinen) → siirtymä → paluu wrapissa
- Poikkeusliput per henkilö: oma_auto, ei_paluuta, siirtyy
- Generoidut rivit `generoitu=true`; uudelleengenerointi korvaa VAIN omat
  rivinsä, ei koskaan käsin lisättyjä
- Endpoint: `POST /paivat/{id}/generoi-tehtavat`

## Vaihe C — V1.1 Bufferit (pieni sessio, spec §8)

- `kuski.pickup_bufferi_min`, `henkilo.nouto_bufferi_min` + migraatio
- Transit-callback: noutosolmun kestoon molemmat bufferit
- Näkyvyys: henkilöbufferi vain TUOTANTO/KOORDI (ei tulosteisiin, ei kuskeille)

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

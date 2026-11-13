# Ajuri

Ajuri optimoi kuvausryhmän päivittäiset kuljetukset: kuka noudetaan mistä,
kuka ajaa kenetkin, ja paljonko päivä maksaa. Elokuva- ja tv-tuotannoissa
tämä ajolista tehdään yleensä käsin Excelissä ja Google Mapsissa — työ vie
tuotantokoordinaattorilta tunteja, ja suunnitelma joudutaan tekemään
uudestaan useita kertoja päivässä kun joku sairastuu, lento myöhästyy tai
kuvausjärjestys muuttuu. Ajuri tekee saman laskennan sekunneissa ja
tallentaa jokaisen version, jotta muutoksen voi jäljittää.

![demo](docs/demo.png)

## Miksi tämä on vaikea ongelma

Kyse ei ole pelkästä reitinoptimoinnista, vaan aikataulutetusta
kuljetustehtävästä useilla samanaikaisilla rajoitteilla:

- **Aikaikkunat.** Jokaisella henkilöllä on call time (milloin pitää olla
  paikalla), osalla myös aikaisin nouto- tai viimeisin perilläoloaika
  (esim. lento laskeutuu tiettyyn kellonaikaan). Ketään ei saa jättää
  odottamaan tuntia autoon eikä myöhästyttää settiin.
- **Kapasiteetti.** Auton mukavuuspaikat rajaavat kuinka moni mahtuu
  samaan kyytiin — ja osa henkilöistä ei saa jakaa kyytiä kenenkään
  kanssa (esim. aikataulusyistä tai tuotannollisista syistä).
- **Kuskien sopimustyypit ja ylityöportaat.** Kuukausipalkkaisen kuskin
  käyttö on lähes ilmaista 8 tuntiin asti, päiväpalkkainen maksaa aina
  koko päivän hinnan heti kun häntä käytetään lainkaan, ja
  tuntipalkkaisella extralla on 4 tunnin minimiveloitus. Kaikilla
  ylityöportaat 8–10 h ja yli 10 h eri kertoimin. Halvin ratkaisu ei ole
  aina se, jossa on vähiten kuskeja.
- **Päivänsisäiset siirtymät.** Kuvauspaikka voi vaihtua kesken päivän,
  ja samat autot hoitavat sekä aamun noudot että illan paluukyydit —
  reitit pitää ketjuttaa koko päivän ajalta, ei vain yhtä siirtymää
  kerrallaan.
- **Suunnitelma ei pysy tehtynä.** Kun tilanne muuttuu kesken päivän, jo
  ajetut keikat on lukittava ja loput suunniteltava uusiksi niin, ettei
  pieni muutos myllää koko loppupäivää. Jokainen versio on säilyttävä
  sellaisenaan, jotta jälkikäteen voi tarkistaa minkä listan mukaan
  mentiin.

## Esimerkkitulos

Repossa on seed-skripti (`python -m app.seed`), joka luo yhden
realistisen kuvauspäivän oikeilla pääkaupunkiseudun koordinaateilla: 19
tehtävää (7 henkilön noudot ja paluukyydit, lounashaku, rekvisiitan haku,
lentokenttänouto aikaikkunalla) ja 5 kuskia eri sopimustyypeillä.
Henkilökyydit on merkitty generoiduiksi, joten "Generoi tehtävät" korvaa
ne eikä tuplaa niitä. Näin optimointia ajettiin oikeasti seedin aiemmalla
16 tehtävän versiolla, jossa työryhmän kyydit olivat yhdistettyinä:

| Kuskikokoonpano | Kokonaiskustannus |
|---|---|
| 3 kuskia tarjolla (2× kuukausi + päiväpalkka/minibussi) | 426,07 € |
| 4 kuskia tarjolla (+ tuntipalkkainen extra) | **346,80 €** |
| 5 kuskia tarjolla (+ ilta-ajan kuukausikuski) | **260,33 €** |

Kolme löydöstä, jotka eivät ole itsestään selviä ilman laskentaa:

1. **Neljäs kuski oli halvempi kuin kolmas.** Kun tuntipalkkainen extra
   otettiin mukaan vaihtoehtoihin, optimoija korvasi sillä kalliimman
   päiväpalkkaisen minibussikuskin — enemmän vaihtoehtoja johti
   halvempaan lopputulokseen, ei kalliimpaan.
2. **Tuntipalkkainen extra oli halvempi kuin päiväpalkkainen kuski**
   yhden lyhyen illan keikan hoitamiseen: 4 tunnin minimiveloitus voitti
   päiväpalkkaisen kiinteän 8 tunnin hinnan.
3. **Yksi lisäkuski pudotti hinnan 260 euroon.** Ilta-ajaksi (klo 18
   alkaen) tarjolla oleva kuukausikuski hoiti illan yksinäiskyydin
   nollakustannuksella, koska hänen palkkansa on jo muutenkin maksettu —
   ja korvasi näin tuntipalkkaisen extran kokonaan.

Kaikki 16 tehtävää sijoittuivat joka kokoonpanossa. Halvimmassa
ratkaisussa kaksi kuskia venyi yli 8 tunnin vuoroon (12,15 h ja 10,77 h),
mikä laukaisi ylityölisät — optimoija hyväksyi sen, koska se oli silti
halvempaa kuin lisäkuskin palkkaaminen.

## Tekninen toteutus

**Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0 (async), PostgreSQL 16,
Alembic, Google OR-Tools, OSRM, Nominatim, Photon, React 19 + Vite,
Docker Compose, GitHub Actions.

**Arkkitehtuuri:**

```
app/
  models.py              SQLAlchemy 2.0 -mallit
  schemas.py             Pydantic v2 -skeemat (Create/Read erikseen)
  rooli.py               Roolin lähde (X-Rooli-header, ks. alempana)
  response_filter.py     Roolipohjainen kenttäsuodatus vastauksiin
  routers/               REST-endpointit (CRUD, generointi, optimointi,
                         versiot ja versiodiffi, osoite-ehdotukset)
  services/
    optimoija.py           OR-Tools-malli, syyanalyysi, skenaariot
    laskenta.py            Optimoinnin ajo erillisessä prosessipoolissa
    kustannus.py           Sopimustyyppikohtainen kustannuslaskenta
    matka_cache.py         Ajoaikojen välimuisti
    router_client.py       Reititys-API-abstraktio (OSRM)
    geocoder_client.py     Geokoodaus-API-abstraktio (Nominatim)
    geokoodaus_cache.py    Osoitteiden geokoodausvälimuisti
    osoite_ehdottaja.py    Osoite-ehdotukset kirjoittaessa (Photon)
  seed.py                Demo-kuvauspäivän generointi
alembic/                 Tietokantamigraatiot
tests/                   Pytest-testit
frontend/src/            React-frontti: Rekisteri, Pohjatiedot, Tehtävät,
                         Optimointi (tulos, tulostus, versiodiffi,
                         kuski pois pelistä), yhteinen OsoiteKentta
scripts/                 Windowsin käynnistys- ja sammutusskriptit
docs/                    Spesifikaatiot, tuotekartta, käynnistysohjeet
.github/workflows/ci.yml CI: pytest, Docker Compose + migraatiot, frontti
ajolista_optimoija.py    Alkuperäinen OR-Tools-prototyyppi (itsenäinen)
```

**Optimointimalli:** kuljetustehtävät mallinnetaan
pickup-and-delivery-ongelmana aikaikkunoilla (VRPTW) OR-Toolsin
reitityssolverilla. Jokainen tehtävä on nouto- ja jättösolmupari, jotka
on sidottu samaan ajoneuvoon ja oikeaan järjestykseen; kuskit ovat
solmugraafin ajoneuvoja, jotka lähtevät kotoa (tai edellisen version
viimeisestä lukitusta keikasta reoptimoinnissa) ja palaavat sinne.
Kapasiteettirajoite on toteutettu per-ajoneuvo-kysyntäfunktiolla, mikä
mahdollistaa myös "ei kimppakyytiä" -rajoitteen (kysyntä = koko auton
kapasiteetin täyttävä silloin kun kyseistä henkilöä kuljetetaan).
Kustannusmalli ohjaa hakua sopimustyyppikohtaisilla kiinteillä ja
ylityöporrastetuilla kustannuksilla; tarkka euromäärä lasketaan
ratkaisun jälkeen erikseen.

**Palveluaikabufferit.** Kuskilla ja henkilöllä voi olla oma
puskuriaika (`kuski.pickup_bufferi_min`, `henkilo.nouto_bufferi_min`) —
toisilla noudot vievät järjestelmällisesti kauemmin, ja joku on
tyypillisesti myöhässä. Bufferit lisätään noutosolmun kestoon
ajoneuvokohtaisilla transit-callbackeilla, mutta **vain aikadimensioon,
ei kaarikustannukseen**: muuten optimoija alkaisi systemaattisesti
välttää kuskia, josta on kirjattu realistista dataa.

**Ulkoiset palvelut abstraktion takana.** Reititys (OSRM) ja geokoodaus
(Nominatim) ovat kumpikin oman rajapintansa takana ja kumpikin
välimuistitettu tietokantaan pistepareittain ja osoitteittain — samat
hotellit, lokaatiot ja osoitteet toistuvat päivästä toiseen, joten
ulkoista palvelua kutsutaan harvoin. Nominatim-toteutus noudattaa
palvelun käyttöehtoja (yksilöivä User-Agent, enintään 1 kutsu/s).
Käyttöehdot kieltävät myös automaattitäydennyksen, joten osoitekentän
ehdotukset kirjoittaessa tulevat Photonista (sama OpenStreetMap-data,
tehty tähän käyttöön) omassa `OsoiteEhdottaja`-abstraktiossaan.
Valitun ehdotuksen koordinaatit tallentuvat suoraan, joten geokoodausta
ei tarvita lainkaan. Tulokset painotetaan pääkaupunkiseudulle mutta
niitä ei rajata, koska yhteistuotannoissa tarvitaan myös ulkomaisia
osoitteita.
Testeissä käytetään deterministisiä toteutuksia, joten yksikään testi ei
kosketa verkkoa. Julkinen OSRM-demopalvelin ei sovi tuotantoon (ei
SLA:ta, rate limit) — vaihto omaan instanssiin tai kaupalliseen
palveluun on yksi uusi luokka ja asetusmuutos.

**Optimointi omassa prosessissaan.** OR-Toolsin C++-ratkaisija pitää
Pythonin GIL-lukkoa koko ratkaisun ajan, joten samassa prosessissa
ajettuna se pysäytti koko API:n optimoinnin ajaksi (noin minuutti
skenaariovertailun kanssa) — muut välilehdet eivät saaneet vastausta.
Siirto säikeeseen ei auttanut juuri GIL:n takia. Pääratkaisu,
sijoittamattomien syyanalyysi ja skenaariovertailu ajetaan siksi
`ProcessPoolExecutor`issa (`app/services/laskenta.py`), pääratkaisu ja
vertailu rinnakkain. Syyanalyysi ratkaisee jokaiselle sijoittamattomalle
tehtävälle yhden tehtävän ongelman per kuski ("ehtisikö tämä kuski
edes yksinään?"), ja sille riittää 1 sekunnin aikaraja täyden aikarajan
sijaan. Saman päivän päällekkäinen optimointi palauttaa 409:n, jotta
kaksi ajolistaversiota ei synny kilpasilla. Vika löytyi toistamalla
Windowsin `spawn`-käynnistys ja katsomalla jumittunutta prosessia
py-spyllä. Regressiotestit pitävät GIL:ää kuten OR-Tools, ja ne kaatuvat
säieversiolla.

**Versiointi ja soft delete.** Jokainen optimointiajo tallentuu omana
`ajolista_versio`-rivinään, eikä mitään kirjoiteta vanhan päälle.
Julkaistut versiot saavat alan call sheet -käytännön mukaisen
värikoodin (WHITE → BLUE → PINK → YELLOW, sen jälkeen numeroituna) —
blue call sheet, blue ajolista. Tehtäviä, henkilöitä, kuskeja ja
lokaatioita ei koskaan poisteta kovaa kautta, koska niihin viittaa
aiempien versioiden keikkoja: `DELETE` merkitsee rivin passiiviseksi,
jolloin se katoaa listauksista mutta vanha ajolista pysyy ehjänä.

## Käynnistys

Windowsilla helpoin tapa on tuplaklikata juuren `Käynnistä AJURI.cmd` (ja sammuttaa `Sammuta AJURI.cmd`). Tarkemmat ohjeet: [docs/ajuri-kaynnistys.md](docs/ajuri-kaynnistys.md).

**Backend (Docker Compose):**

```
cp .env.example .env
docker compose up --build
docker compose exec app alembic upgrade head
docker compose exec app python -m app.seed
```

API: http://localhost:8000, Swagger-UI: http://localhost:8000/docs.
Postgres on mäpätty isäntäkoneen porttiin 5433 (ei 5432), koska koneella
voi olla jo natiivi PostgreSQL-palvelu portissa 5432.

**Backend paikallisesti ilman Dockeria** (vaatii käynnissä olevan
Postgresin, esim. `docker compose up -d db`):

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

**Frontend:**

```
cd frontend
cp .env.example .env
npm install
npm run dev
```

Avaa http://localhost:5173. Vaatii backendin käynnissä portissa 8000 —
CORS on sallittu porttiin 5173 (`app/config.py: cors_origins`).

Frontin välilehdet kulkevat työn järjestyksessä:

- **Rekisteri** — tuotannon henkilöt (näyttelijät, työryhmä) ja kuskit.
  Osoitekenttä ehdottaa osoitteita kirjoittaessa.
- **Pohjatiedot** — kuvauspäivän kokoaminen: call, lounas ja wrap,
  päivän lokaatiot siirtymineen sekä mukana olevat henkilöt ja kuskit autoineen
- **Tehtävät** — "Generoi tehtävät" call timeista, generoitujen ja käsin
  lisättyjen erottelu sekä pikapohjat (lounashaku, kortit, lentokenttä)
- **Optimointi** — optimoi päivä ja katso tulos per kuski aikajanoineen,
  kustannuksineen, sijoittamattomien syineen ja skenaariovertailuineen.
  Lisäksi julkaisu värikoodilla, A4-tulostusversio ilman kustannuksia,
  versiodiffi ("Näyttelijä 2: nouto 7.40 → 8.10") ja "kuski pois pelistä"
  -hätänappi, joka optimoi loppupäivän uudelleen kuitatut keikat
  lukittuina. Päivän viimeisin ajolista näkyy heti, ja kesken oleva
  laskenta jatkuu, vaikka sivun päivittäisi.

Yksityiskohtaiset käynnistys- ja vianetsintäohjeet:
[docs/ajuri-kaynnistys.md](docs/ajuri-kaynnistys.md).

## Testit

```
pytest
```

148 testiä, ajavat SQLite-muistikannalla (ei vaadi Postgresia).
Ulkoiset palvelut korvataan deterministisillä toteutuksilla, joten
testit eivät kosketa verkkoa.

Painopisteet:

- **Kustannuslogiikka** yksikkötasolla: jokainen sopimustyyppi ja
  ylityöporras erikseen
- **OR-Tools-malli** synteettisillä skenaarioilla: aikaikkunat,
  kapasiteetti, "ei kimppakyytiä", kiinteä kuski, bufferit,
  sijoittamattomien syykoodit
- **Regressiotesti kokonaisella vakiopäivällä** (17 tehtävää, 5 kuskia)
  — tämä vahtii optimoinnin *laatua*, ei vain sitä ettei koodi kaadu
- **Reoptimoinnin reunatapaukset**: lukitun keikan tehtävä tai kuski on
  passivoitu myöhemmin — ei saa kaatua, ja keikan tiedot on silti
  näytettävä oikein
- **Rajapintatestit**: CRUD, tehtävägenerointi, version julkaisu ja
  värikoodaus, versiodiffi, keikan kuittaus, kuski pois pelistä,
  roolisuodatus, geokoodaus ja sen välimuisti, osoite-ehdotukset, soft delete
- **Rinnakkaisuus**: optimointi ei jumita muita pyyntöjä (testi pitää
  GIL:ää kuten OR-Tools ja kaatuu, jos laskenta ajetaan säikeessä), ja
  saman päivän päällekkäinen optimointi estetään

Migraatiot ajetaan ja `alembic check` varmistetaan erikseen oikeaa
PostgreSQL:ää vasten, koska testit luovat taulut suoraan malleista.

**CI (GitHub Actions)** ajaa jokaiselle PR:lle kolme tarkistusta: pytest,
Docker Compose -buildin migraatioineen ja `alembic check`ineen oikeaa
PostgreSQL:ää vasten sekä frontin lintin ja buildin. `main` on suojattu,
joten muutokset kulkevat aina PR:nä ja vihreän CI:n kautta.

## Roolit ja X-Rooli-header

API:ssa on kolme roolia (`KayttajaRooli`-enum): TUOTANTO, KOORDI ja KUSKI.
TUOTANTO ja KOORDI näkevät kaiken. KUSKI-roolilta piilotetaan
vastauksista kustannuskentät (`ajolista_versio.kokonaiskustannus_eur`,
kuskikohtainen `lisakustannus_eur`, koko skenaariovertailu) sekä
henkilö-/kuskikohtaiset bufferi- ja aikapreferenssikentät
(`henkilo.nouto_bufferi_min`, `henkilo.max_etuajassa_min`,
`kuski.pickup_bufferi_min`, `kuski.tuntihinta_eur`) — nämä eivät katoa
vain `null`:iksi, vaan puuttuvat JSON-vastauksesta kokonaan.

Rooli luetaan toistaiseksi (kunnes ROADMAPin vaihe K on valmis)
`X-Rooli`-headerista (`app/rooli.py`),
oletuksena TUOTANTO jos header puuttuu tai sen arvo on tuntematon:

```
curl -H "X-Rooli: kuski" http://localhost:8000/henkilot
```

**Tämä ei ole turvaominaisuus.** `X-Rooli` on asiakkaan itsensä
asettama header — kuka tahansa voi pyytää TUOTANTO-näkymän vaihtamalla
headerin arvon. Se on väliaikainen UI:n karsintamekanismi ennen
autentikointia (ks. [docs/tuotekartta.md](docs/tuotekartta.md) V2:
"Käyttäjähallinta + autentikointi"). Kun JWT-pohjainen autentikointi
rakennetaan, vain `app/rooli.py`:n `nykyinen_rooli`-funktion sisältö
vaihtuu (header → JWT-claim) — itse kenttäsuodatus
(`app/response_filter.py`) ja kaikki sitä käyttävät reitittimet pysyvät
koskemattomina.

Myös huomio: **Swagger-dokumentaatio (`/docs`) näyttää aina kaikki
kentät roolista riippumatta** — endpointtien `response_model` on jätetty
paikoilleen dokumentaatiota varten, mutta ajonaikainen suodatus tapahtuu
sen ohi (`JSONResponse` palautetaan suoraan). Swaggerin "Try it out"
-kutsu näyttää silti oikean, suodatetun JSON-vastauksen — vain skeeman
kuvaus (mitä kenttiä VOISI olla) on aina täysi.

## Tilanne ja jatkokehitys

**Valmiina:** perusdatan ja päiväkohtaisen datan CRUD ja niiden
syöttönäkymät, tehtävägenerointi call timeista, optimointi
kustannuslaskentoineen, syyanalyyseineen ja skenaariovertailuineen
omassa prosessissaan, reoptimointi ("kuski pois pelistä"), versiointi,
värikoodaus ja versiodiffi, tulostusversio, osoite-ehdotukset
kirjoittaessa, soft delete kaikelle datalle, palveluaikabufferit,
roolipohjainen kenttäsuodatus ja geokoodaus välimuisteineen.

**Seuraavaksi** ([ROADMAP.md](ROADMAP.md)):

1. **Kirjautuminen** — salasanat (argon2), JWT ja roolit tokenista
   `X-Rooli`-headerin sijaan
2. **Kovennukset** — tuotantoasetukset ilman oletussalaisuuksia,
   pyyntörajoitukset ja syötteiden rajat
3. **Julkaisu demoksi** — Render, demotila ja arkkitehtuurikuvaus
4. **Kuskin mobiilinäkymä** — kuski näkee puhelimesta vain oman päivänsä
5. **Excel-tuonti** rekisteriin esikatselulla

Pidemmän aikavälin suunta ja perustelut ovat tiedostossa
[docs/tuotekartta.md](docs/tuotekartta.md). Optimoijan rajapinta,
kustannusmalli, rajoitteet ja reunatapaukset on speksattu erikseen
tiedostossa [docs/optimoija-spec.md](docs/optimoija-spec.md).

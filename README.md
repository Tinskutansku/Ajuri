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
realistisen kuvauspäivän oikeilla pääkaupunkiseudun koordinaateilla: 16
tehtävää (henkilönoutoja, paluukyytejä, lounashaku, rekvisiitan haku,
lentokenttänouto aikaikkunalla) ja 5 kuskia eri sopimustyypeillä. Näin
optimointia ajettiin oikeasti tällä datalla:

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
Alembic, Google OR-Tools, OSRM, Nominatim, React + Vite, Docker Compose.

**Arkkitehtuuri:**

```
app/
  models.py              SQLAlchemy 2.0 -mallit
  schemas.py             Pydantic v2 -skeemat (Create/Read erikseen)
  rooli.py               Roolin lähde (X-Rooli-header, ks. alempana)
  response_filter.py     Roolipohjainen kenttäsuodatus vastauksiin
  routers/               REST-endpointit (CRUD, generointi, optimointi)
  services/
    optimoija.py           OR-Tools-malli, syyanalyysi, skenaariot
    kustannus.py           Sopimustyyppikohtainen kustannuslaskenta
    matka_cache.py         Ajoaikojen välimuisti
    router_client.py       Reititys-API-abstraktio (OSRM)
    geocoder_client.py     Geokoodaus-API-abstraktio (Nominatim)
    geokoodaus_cache.py    Osoitteiden geokoodausvälimuisti
  seed.py                Demo-kuvauspäivän generointi
alembic/                 Tietokantamigraatiot
tests/                   Pytest-testit
frontend/                Vite + React -frontti
docs/                    Spesifikaatiot, tuotekartta, käynnistysohjeet
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
Testeissä käytetään deterministisiä toteutuksia, joten yksikään testi ei
kosketa verkkoa. Julkinen OSRM-demopalvelin ei sovi tuotantoon (ei
SLA:ta, rate limit) — vaihto omaan instanssiin tai kaupalliseen
palveluun on yksi uusi luokka ja asetusmuutos.

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

Frontissa on kaksi välilehteä: **Rekisteri** (henkilöiden ja kuskien
ylläpito) ja **Optimointi** (valitse kuvauspäivä, optimoi, katso
tulos per kuski aikajanoineen, kustannuksineen ja skenaariovertailuineen).
Päiväkohtaiset syöttönäkymät ovat työn alla — ks.
[docs/tuotekartta.md](docs/tuotekartta.md).

Yksityiskohtaiset käynnistys- ja vianetsintäohjeet:
[docs/ajuri-kaynnistys.md](docs/ajuri-kaynnistys.md).

## Testit

```
pytest
```

103 testiä, ajavat SQLite-muistikannalla (ei vaadi Postgresia).
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
  värikoodaus, keikan kuittaus, roolisuodatus, geokoodaus ja sen
  välimuisti, soft delete

Migraatiot ajetaan ja `alembic check` varmistetaan erikseen oikeaa
PostgreSQL:ää vasten, koska testit luovat taulut suoraan malleista.

## Roolit ja X-Rooli-header

API:ssa on kolme roolia (`KayttajaRooli`-enum): TUOTANTO, KOORDI ja KUSKI.
TUOTANTO ja KOORDI näkevät kaiken. KUSKI-roolilta piilotetaan
vastauksista kustannuskentät (`ajolista_versio.kokonaiskustannus_eur`,
kuskikohtainen `lisakustannus_eur`, koko skenaariovertailu) sekä
henkilö-/kuskikohtaiset bufferi- ja aikapreferenssikentät
(`henkilo.nouto_bufferi_min`, `henkilo.max_etuajassa_min`,
`kuski.pickup_bufferi_min`, `kuski.tuntihinta_eur`) — nämä eivät katoa
vain `null`:iksi, vaan puuttuvat JSON-vastauksesta kokonaan.

Rooli luetaan toistaiseksi `X-Rooli`-headerista (`app/rooli.py`),
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

**Valmiina:** perusdatan ja päiväkohtaisen datan CRUD, tehtävägenerointi
call timeista, optimointiservice kustannuslaskentoineen,
reoptimoinnilla ja syyanalyysilla, versiointi ja värikoodaus, soft
delete kaikelle datalle, palveluaikabufferit, roolipohjainen
kenttäsuodatus, geokoodaus välimuisteineen, sekä frontin Rekisteri- ja
Optimointi-välilehdet.

**Seuraavaksi:** päiväkohtaiset syöttönäkymät, osoitteen
automaattitäydennys, tulostusversio ja versiodiffi. Kaikki jäljellä
oleva työ on kuvattu järjestyksessä ja perusteluineen tiedostossa
[docs/tuotekartta.md](docs/tuotekartta.md).

Optimoijan rajapinta, kustannusmalli, rajoitteet ja reunatapaukset on
speksattu erikseen tiedostossa
[docs/optimoija-spec.md](docs/optimoija-spec.md).

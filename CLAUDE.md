# AJURI — ohjeet Claudelle

Tämä tiedosto on Tanjan esihyväksyntä. Se kertoo mitä saat tehdä
kysymättä ja milloin pitää pysähtyä. Lue tämä ja `ROADMAP.md` jokaisen
ajon alussa. Tuotteen kokonaiskuva on `docs/tuotekartta.md`:ssä.

Tanja lukee tulokset aamulla puhelimelta. Kirjoita PR:t ja yhteenvedot
niin, että ne ymmärtää GitHubin mobiilisovelluksesta ilman koodin
avaamista. Suomeksi.

## Työnkulku

- **Älä koskaan pushaa `main`-haaraan.** Kaikki muutokset omaan
  haaraan `claude/<lyhyt-kuvaus>` ja PR:nä. Tanja mergeää itse.
- **Yksi ROADMAP-kohta = yksi PR.** Jos kohta on liian iso yhteen
  ajoon, jaa se ROADMAPissa alakohtiin ja tee ensimmäinen.
- **Avoimia Claude-PR:iä enintään 2.** Jos raja on täynnä, käsittele
  vain avointen PR:ien review-kommentit ja CI-korjaukset.
- Jos seuraava kohta riippuu mergeämättömästä PR:stä, haarauta sen
  PR:n haarasta (stacked PR) ja kerro se PR:n kuvauksessa.
- Päivitä ROADMAPin tila samassa PR:ssä (`[ ]` → `[PR #n]`).
- Commit-viestit suomeksi, imperatiivissa ("Lisää …", "Korjaa …").

## Valmiin määritelmä

PR on valmis vasta kun kaikki nämä pätevät.

1. `pytest` menee läpi paikallisesti (SQLite in-memory, ei vaadi
   Dockeria eikä verkkoa).
2. Jos koskit `frontend/`-hakemistoon: `npm run lint` ja
   `npm run build` menevät läpi.
3. Uudelle backend-toiminnallisuudelle on testi. Frontendissä ei ole
   testikehystä, joten kerro PR:ssä miten muutoksen voi kokeilla käsin.
4. GitHub Actions (`.github/workflows/ci.yml`) on vihreä. CI ajaa myös
   Docker Composen, PostgreSQL-migraatiot ja `alembic check`in, joita
   et voi ajaa itse. Jos CI on punainen, korjaa ennen kuin raportoit
   PR:n valmiiksi.
5. ROADMAP-kohdan hyväksymiskriteerit täyttyvät. Jos jokin jäi
   tekemättä, sano se suoraan.

## Saa tehdä kysymättä

- ROADMAPin seuraavan kohdan toteutus sen kuvauksen mukaisesti
- Uudet endpointit ja frontin näkymät, jotka ROADMAP-kohta kuvaa
- Uudet funktiot `frontend/src/api.js`:ään olemassa oleville endpointeille
- Testien lisääminen ja olemassa olevien testien laajentaminen
- Refaktorointi, joka ei muuta API:n ulkoista käytöstä
- Bugikorjaukset, joihin törmäät matkalla (mainitse PR:ssä)
- Dokumentaatio: README, `docs/`, koodikommentit
- `docs/tuotekartta.md`:n tilan päivitys kun vaihe valmistuu
- Pienet UI-ratkaisut olemassa olevan tyylin mukaisesti
  (`frontend/src/ui.jsx`:n komponentit ja `C`-värit)

## Pysähdy ja kysy (poikkeama)

Näitä et tee, vaikka tehtävä tuntuisi vaativan.

- **Uusi riippuvuus** (`requirements.txt` tai `package.json`)
- **Tietokantaskeeman muutos** tai uusi Alembic-migraatio
- **API-sopimuksen rikkova muutos**: olemassa olevan endpointin polku,
  pakollinen kenttä, vastausmuoto tai statuskoodi muuttuu
- **Optimoijan malli** (`app/services/optimoija.py`): tavoitefunktio,
  rajoitteet, kustannuslogiikka, buffereiden käsittely. Bufferit ovat
  tarkoituksella vain aikadimensiossa, ei kaarikustannuksessa.
- **Roolinäkyvyys** (`app/response_filter.py`, `app/rooli.py`):
  mitä KUSKI-rooli näkee
- **Testin poistaminen, ohittaminen tai heikentäminen** jotta jokin
  menisi läpi
- **Ulkoiset palvelut**: uudet kutsut Nominatimiin, OSRM:ään, Photoniin
  tai muualle. Testeissä aina `FakeGeocoder` / `FakeOsoiteEhdottaja` /
  feikki-RouterClient, ei koskaan oikeaa verkkoa. Nominatimilla ei saa
  tehdä automaattitäydennystä (käyttöehdot), siihen käytetään Photonia.
- Docker-, CI-, deploy- tai salaisuuksiin liittyvät muutokset
- Kaikki, mikä on ristiriidassa `docs/tuotekartta.md`:n tai
  `docs/optimoija-spec.md`:n kanssa
- Tilanne, jossa ROADMAP-kohdan voi tulkita kahdella merkittävästi
  eri tavalla

## Poikkeamaprotokolla

Kun törmäät johonkin "Pysähdy ja kysy" -listan asiaan:

1. Älä arvaa äläkä toteuta sitä osaa.
2. Jos muu osa tehtävästä onnistuu ilman sitä, tee se ja avaa PR.
   Muussa tapauksessa avaa issue.
3. Lisää PR:ään tai issueen label **`needs-decision`** ja kirjoita
   kuvauksen alkuun osio:

   ```
   ## ⚠ Päätös tarvitaan
   **Mitä:** yksi lause
   **Miksi:** miksi tehtävä vaatii tämän
   **Vaihtoehdot:**
   A) … (oma suositus, perustelu)
   B) …
   **Vastaa kommentilla "A" tai "B" tai omalla ohjeella.**
   ```

4. Merkitse ROADMAP-kohta `[odottaa päätöstä #n]` ja siirry seuraavaan
   kohtaan, joka ei riipu tästä.

Seuraavassa ajossa lue `needs-decision`-PR:ien ja -issueiden kommentit.
Jos Tanja on vastannut, toteuta päätös ja poista label.

## Projektin käytännöt

- Python 3.12+ (Docker-image 3.12, kehitys 3.13), FastAPI, async SQLAlchemy 2
- Koodi, muuttujat ja kommentit suomeksi kuten muuallakin projektissa
- Testit: `pytest` juuresta, `tests/conftest.py` antaa `client`- ja
  `db_session`-fixturet SQLite-muistikannalla ja `FakeGeocoder`in
- Soft delete kaikilla resursseilla: `aktiivinen`-kenttä, listaukset
  piilottavat passiiviset oletuksena
- Ulkoiset palvelut aina abstraktion takana (`GeocoderClient`,
  `RouterClient`)
- Frontend: React 19 + Vite, ei TypeScriptiä, ei UI-kirjastoa;
  tyylit inline `ui.jsx`:n apureilla

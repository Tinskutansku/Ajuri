# ROADMAP — yöajojen tehtävälista

Claude ottaa ylimmän kohdan, jonka tila on `[ ]`. Tanja hyväksyy tämän
listan etukäteen. Järjestyksen tai sisällön muutos tehdään muokkaamalla
tätä tiedostoa. Tarkemmat taustat ovat `docs/tuotekartta.md`:ssä.

Jos kohdassa on rivi **Esihyväksytty**, siinä luetellut asiat saa tehdä
kysymättä tässä kohdassa, vaikka ne ovat CLAUDE.md:n "Pysähdy ja kysy"
-listalla. Kaikki muu listan asia vaatii edelleen päätöksen.

Tilat
- `[ ]` tekemättä
- `[PR #n]` PR auki, odottaa mergeä
- `[odottaa päätöstä #n]` poikkeama, ks. PR tai issue
- `[x]` mergetty

---

## Valmiit (5.–13.11.2026)

G1 Pohjatiedot · G2 Tehtävät · H1+H2 osoite-ehdotukset (Photon) ·
I1 tulostusversio · I2 kuski pois pelistä · J1+J2 versiodiffi ·
503-virhe tietokantakatkoon · `GET /` · kenttäotsikot Rekisteriin ·
optimointi muistaa tuloksen · seedin kyydit generoiduiksi ·
optimointi omassa prosessissaan (#12, #13) · käynnistysnappi (#4–#11)

Tarkat kuvaukset ovat git-historiassa ja PR:issä.

---

## Vaihe K — Kirjautuminen (roolit oikeasti voimaan)

Nyt rooli luetaan `X-Rooli`-otsakkeesta, jonka kuka tahansa voi asettaa
(`app/rooli.py`: "EI TURVAOMINAISUUS"). Tämä vaihe on edellytys sille,
että kukaan muu kuin Tanja käyttää sovellusta.

**Esihyväksytty koko vaiheelle (Tanja 13.11.):** riippuvuudet `PyJWT` ja
`argon2-cffi`; `kayttaja`-taulun laajennus (salasana-hash, aktiivinen,
viimeksi kirjautunut) ja sen Alembic-migraatio; roolin lukeminen tokenista
`X-Rooli`-otsakkeen sijaan. Roolikohtainen kenttien näkyvyys
(`response_filter.py`) pysyy ennallaan.

### K1 `[ ]` Backend: kirjautuminen ja token
- `kayttaja`-tauluun `salasana_hash` (argon2), `aktiivinen`,
  `viimeksi_kirjautunut` + migraatio
- `POST /auth/kirjaudu` (email + salasana) → JWT (HS256, voimassa 12 h,
  sisältää käyttäjä-id:n, roolin ja tuotanto-id:n). Väärä tunnus tai
  salasana → aina sama 401-viesti (ei paljasteta kumpi oli väärin).
- `GET /auth/mina` → kirjautunut käyttäjä ilman hashia
- `JWT_SECRET` ympäristömuuttujasta. Kehityksessä (`AJURI_YMPARISTO=dev`)
  saa olla oletus, muuten puuttuva salaisuus kaataa käynnistyksen.
- Komentorivityökalu ensimmäisen käyttäjän luontiin:
  `python -m app.luo_kayttaja --email ... --rooli tuotanto` (kysyy salasanan)
- Seed luo demokäyttäjät (tuotanto, koordi, kuski) tunnetuilla
  demosalasanoilla, jotka kerrotaan README:ssä
- **Valmis kun:** testit kirjautumiselle (oikea, väärä salasana, tuntematon
  email, passivoitu käyttäjä), token-sisällölle ja migraatiolle (CI:n
  `alembic check`)

### K2 `[ ]` Backend: kaikki reitit vaativat kirjautumisen
- `nykyinen_rooli` lukee roolin tokenista (kutsupaikat eivät muutu, ks.
  `app/rooli.py`:n ohje). `X-Rooli` poistuu.
- Kaikki reitit vaativat voimassa olevan tokenin, paitsi `GET /`,
  `GET /health`, `POST /auth/kirjaudu` ja kehityksessä `/docs`
- Puuttuva tai vanhentunut token → 401, väärä rooli muokkaukseen → 403
  (KUSKI ei saa muokata mitään)
- Käyttäjä näkee vain oman tuotantonsa datan (`tuotanto_id` tokenista)
- `tests/conftest.py`: `client` kirjautuu oletuksena TUOTANTO-roolilla,
  ja testeille apufixturet muille rooleille
- **Valmis kun:** testi jokaiselle reitille ilman tokenia (401), KUSKI-
  muokkaukselle (403) ja toisen tuotannon datalle (404). Kaikki vanhat testit
  menevät läpi kirjautuneena.

### K3 `[ ]` Frontend: kirjautumissivu
- Kirjautumissivu (email, salasana, näkyvät kenttäotsikot), uloskirjautuminen
  yläpalkista, kirjautuneen nimi ja rooli näkyviin
- Token muistiin ja `sessionStorage`en (ei `localStorage`: välilehden
  sulkeminen kirjaa ulos). `api.js` lisää `Authorization`-otsakkeen.
- 401 → takaisin kirjautumissivulle viestillä "Istunto vanheni"
- KUSKI-roolille piilotetaan muokkausnapit (backend estää ne joka tapauksessa)
- **Valmis kun:** lint + build läpi, kuvakaappaukset kirjautumissivusta
  leveänä ja mobiilina

## Vaihe L — Kovennukset

**Esihyväksytty (Tanja 13.11.):** riippuvuus `slowapi`.

### L1 `[ ]` Tuotantoasetukset ja turvallinen oletus
- `AJURI_YMPARISTO` = `dev` | `prod`. Prodissa käynnistys kaatuu selkeään
  virheeseen, jos `JWT_SECRET` puuttuu tai on lyhyt, tai jos tietokannan
  salasana on `ajuri`.
- Prodissa: `/docs` ja `/openapi.json` pois, CORS vain `CORS_ORIGINS`-
  muuttujan osoitteet, virhevastauksissa ei tracebackeja eikä SQL:ää
- Turvaotsakkeet (`X-Content-Type-Options`, `Referrer-Policy`,
  `X-Frame-Options`)
- **Valmis kun:** testit prod-asetusten tarkistuksille ja otsakkeille

### L2 `[ ]` Pyyntörajoitukset
- `POST /auth/kirjaudu`: esim. 5 yritystä / min / IP → 429
- `GET /osoitteet/ehdota`: esim. 60 / min / käyttäjä (Photonin
  reilun käytön periaate)
- **Valmis kun:** testit 429-rajoille

### L3 `[ ]` Syötteiden rajat
- Tarkista, että kaikilla merkkijonokentillä on `max_length` ja numeroilla
  järkevät rajat (esim. henkilömäärä, aikaraja). Lisää puuttuvat.
- **Valmis kun:** testit liian pitkille ja negatiivisille arvoille (422)

## Vaihe M — Julkaisu demoksi (portfolio)

**Esihyväksytty (Tanja 13.11.):** deploy-asetukset (Render-blueprint,
ympäristömuuttujat, käynnistyskomennot). Tanja luo itse tilin ja asettaa
salaisuudet; Claude ei koske niihin.

### M1 `[ ]` Render-julkaisu
- `render.yaml`: backend (Docker), frontend (static site), Render Postgres
- Backend ajaa `alembic upgrade head` ennen käynnistystä
- `VITE_API_BASE` frontin buildiin, `CORS_ORIGINS` backendille
- `docs/julkaisu.md`: Tanjan askeleet (tili, blueprint, salaisuudet,
  demodatan seed), ja tieto ilmaisen tason rajoista (uniminen, tietokannan
  vanheneminen)
- Julkinen OSRM-demopalvelin ja Photon kelpaavat demoon. Rajat
  kirjataan dokumenttiin.
- **Valmis kun:** CI buildaa tuotantoversion, ja ohjeen mukaan julkaisu
  onnistuu (Tanja testaa)

### M2 `[ ]` Demotila
- Kirjautumissivulla prodissa "Kokeile demoa" -napit (tuotanto / kuski),
  vain jos `DEMO=true`
- Demodata palautetaan seedillä (komento tai yöllinen ajo, ks. Renderin
  rajat). Kerro PR:ssä, mikä vaihtoehto on käytettävissä ilmaiseksi.
- **Valmis kun:** testi demokirjautumiselle, ja ilman `DEMO=true` napit
  eivät näy

### M3 `[ ]` README ja arkkitehtuurikuvaus
- README: mikä AJURI on, kuvakaappaukset, demo-linkki, teknologiat,
  käynnistys
- `docs/arkkitehtuuri.md`: kerrokset, optimointiputki (Mermaid-kaavio),
  keskeiset ratkaisut ja niiden syyt (abstraktiot, prosessipooli ja GIL,
  versiointi, soft delete, Photon vs. Nominatim)
- **Valmis kun:** Mermaid renderöityy GitHubissa ja linkit toimivat

## Vaihe N — Kuskin mobiilinäkymä (V2 #1)

**Esihyväksytty (Tanja 13.11.):** roolinäkyvyyden muutos niin, että KUSKI
näkee vain omat keikkansa.

### N1 `[ ]` Backend: kuski näkee vain omat keikkansa
- KUSKI-roolin token → `kuski_id` → vain hänen keikkansa julkaistusta
  versiosta. Muiden kuskien keikat ja kustannukset eivät näy.
- **Valmis kun:** testit, ettei KUSKI saa toisen kuskin keikkoja millään
  reitillä

### N2 `[ ]` Frontend: kuskin päivänäkymä puhelimelle
- KUSKI kirjautuu → näkee oman päivänsä: keikat aikajärjestyksessä,
  nouto-osoite karttalinkkinä, kyytiläiset ja puhelinnumerot
- Suunniteltu ensisijaisesti puhelimelle (iso teksti, isot napit)
- **Valmis kun:** lint + build, kuvakaappaus mobiilileveydellä

### N3 `[ ]` "Kyydissä" / "Perillä" -kuittaukset
- Keikalle tila (odottaa / kyydissä / perillä) ja aikaleimat
- Tämä vaatii keikka-tauluun uusia sarakkeita, eli tietokantamuutoksen,
  jota ei ole esihyväksytty. Avaa ensin `needs-decision`-issue, jossa on
  ehdotettu skeema.

## Vaihe O — Excel-tuonti rekisteriin (V2 #2)

**Esihyväksytty (Tanja 13.11.):** riippuvuus `openpyxl`.

### O1 `[ ]` Backend: tuonti esikatselulla
- `POST /tuotannot/{id}/tuonti/esikatselu` (xlsx) → rivit tulkittuina,
  virheet riveittäin, tunnistetut sarakkeet
- `POST /tuotannot/{id}/tuonti` vahvistaa ja tallentaa (osoitteet
  geokoodataan normaalisti)
- Rajat: tiedostokoko, rivimäärä, vain xlsx
- **Valmis kun:** testit esimerkkitiedostoilla (`tests/data/`), myös
  rikkinäinen tiedosto ja puuttuvat sarakkeet

### O2 `[ ]` Frontend: tuonti Rekisteriin
- "Tuo Excelistä" → esikatselutaulukko → vahvista
- Ladattava pohjatiedosto oikeilla sarakkeilla
- **Valmis kun:** lint + build, ohje kokeiluun pohjatiedostolla

## Myöhemmin (ei vielä yöajolla, päätetään yhdessä)

Taksi-fallback · työvuororaportti · korjausehdotukset sijoittamattomille ·
"julkaistu versio vanhentunut" yleisesti · itseoppivat bufferit ·
oma reititinpalvelu · riippuvuuksien tietoturvaskannaus CI:hin
(CI-muutos, vaatii päätöksen). Ks. `docs/tuotekartta.md`.

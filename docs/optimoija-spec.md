# AJURI — Optimoijaservicen speksi (v1)

Tämä dokumentti määrittelee reittioptimoinnin rajapinnan, logiikan ja reunaehdot.
Toteutus: Python + Google OR-Tools (pohja: `ajolista_optimoija.py`), FastAPI-service.
Tietomalli: `models.py` (SQLAlchemy 2.0). Skeemaa ei muuteta ilman erillistä päätöstä.

---

## 1. Endpoint

### POST /paivat/{paiva_id}/optimoi

Request body (kaikki kentät valinnaisia, oletukset alla):

```json
{
  "aikaraja_s": 15,
  "max_etuajassa_min": 30,
  "max_kyytiaika_lisa_min": 25,
  "nyt": null,
  "pohjaversio_id": null,
  "skenaariot": true
}
```

| Kenttä | Merkitys |
|---|---|
| `aikaraja_s` | OR-Tools-ratkaisijan hakuaika sekunteina |
| `max_etuajassa_min` | Kuinka paljon ennen deadlinea saa olla perillä (näyttelijää ei jätetä tunniksi odottamaan) |
| `max_kyytiaika_lisa_min` | Henkilön kyytiaika enintään suora ajoaika + tämä (kimppakyytien kiertelyvara) |
| `nyt` | `"HH:MM"` → päivänsisäinen uudelleenoptimointi tästä hetkestä. `null` = koko päivä. |
| `pohjaversio_id` | Versio, josta lukitut keikat luetaan reoptimoinnissa. `null` + `nyt` annettu → käytä uusinta julkaistua versiota. |
| `skenaariot` | Laske myös kuskimäärävertailu |

Vastaus luo aina uuden `ajolista_versio`-rivin ja palauttaa sen:

```json
{
  "versio_id": 3,
  "versio_nro": 3,
  "kokonaiskustannus_eur": 336.0,
  "kuskit": [
    {
      "paiva_kuski_id": 1,
      "nimi": "Tiina M.",
      "sopimus": "kuukausi",
      "vuoro_alku": "06:59",
      "vuoro_loppu": "14:32",
      "kesto_min": 453,
      "lisakustannus_eur": 0.0,
      "keikat": [
        {
          "keikka_id": 55,
          "tehtava_id": 12,
          "nimi": "Näyttelijä 1 (pääosa)",
          "nouto_klo": "06:59",
          "jatto_klo": "07:12",
          "mista": "Hotelli A", "mihin": "LOC1",
          "kuitattu": false, "lukittu": false
        }
      ]
    }
  ],
  "sijoittamatta": [
    {
      "tehtava_id": 14,
      "nimi": "Paluu: Näyttelijä 2 + 4",
      "syy": "aikaikkuna",
      "selite": "Kaikki autot varattuja 17:30–17:55, nouto ei ehdi ikkunaan"
    }
  ],
  "skenaariot": [
    { "kuskeja_tarjolla": 3, "kuskeja_kaytossa": 3, "kustannus_eur": 336.0, "ratkeaa": true, "halvin": true },
    { "kuskeja_tarjolla": 4, "kuskeja_kaytossa": 4, "kustannus_eur": 353.0, "ratkeaa": true, "halvin": false }
  ]
}
```

MVP on synkroninen. Rajapinta on kuitenkin muotoiltu versio-objektin ympärille,
jotta V2:ssa sama endpoint voi palauttaa heti `{"versio_id": N, "tila": "lasketaan"}`
ja UI pollaa — sopimus ei muutu.

---

## 2. Kustannusmalli

Työaika = ensimmäisestä noudosta viimeiseen jättöön (odottelu välissä lasketaan).
Kotimatkat eivät ole työaikaa. Tuntihinta: kuskin oma tai tuotannon oletus.

| Sopimus | Päivän lisäkustannus |
|---|---|
| `kuukausi` (37,5 h/vko) | 0 € ≤ 8 h asti (peruspalkka maksettu). Ylityöt: 8–10 h ×1,5 · yli 10 h ×2. |
| `paiva` | 8 h × tuntihinta jos käytössä + ylityöt kuten yllä |
| `tunti` (extra) | max(4 h, toteuma) × tuntihinta, portaat 8 h / 10 h kuten yllä |

Optimoinnin tavoitefunktio = päivän lisäkustannus + pieni ajoaikatermi.
Käytännössä: sopimuskuskien tunnit täytetään ensin (ilmaisia 8 h asti),
ylitöitä vältetään, extra otetaan vain jos halvempi kuin ylityöt.
OR-Toolsissa: fixed cost per vehicle sopimuksen mukaan, span cost coefficient,
soft span upper bound 8 h + kvadraattinen sakko 10 h (tarkka € lasketaan jälkikäteen).

Viikkosaldo (37,5 h/vko) EI ole MVP:ssä optimointirajoite — toteutuneet tunnit
tallennetaan `paiva_kuski`-tauluun ja saldo lasketaan raportointiin. V2:ssa saldosta
voi johtaa kuskikohtaisen "tunteja jäljellä ennen ylitöitä" -rajan päivälle.

---

## 3. Rajoitteet (kovat)

1. Perillä `perilla_viimeistaan` mennessä, aikaisintaan `perilla_viimeistaan - max_etuajassa_min` (tai tehtävän oma `perilla_aikaisintaan`)
2. Nouto ikkunassa `[nouto_aikaisintaan, nouto_viimeistaan]` jos annettu
3. Henkilön kyytiaika ≤ suora ajoaika + `max_kyytiaika_lisa_min` (vain jos `henkiloita > 0`)
4. Auton **mukavuuspaikat** = kapasiteetti (max_paikat on hätävara, ei optimoijan käytössä MVP:ssä)
5. `yksin`-lipulla merkittyä ei yhdistetä kimppakyytiin
6. `lukittu_kuski_id` → tehtävä vain tälle kuskille
7. Kuskin vuoro alkaa aikaisintaan `vuoro_aikaisintaan`, päättyy viimeistään `vuoro_viimeistaan` (jos annettu); kova katto 13 h
8. Nouto ja jättö samalla autolla, nouto ennen jättöä

## 4. Uudelleenoptimointi päivän aikana (`nyt` annettu)

1. Lue pohjaversio (`pohjaversio_id` tai uusin julkaistu)
2. **Lukitut keikat** = `kuitattu = true` TAI `nouto_klo < nyt` → kopioidaan uuteen versioon sellaisinaan
3. Kuskin lähtötila optimoinnille = viimeisen lukitun keikan jättöpaikka ja -aika
4. Loput tehtävät ratkaistaan vapaasti
5. **Stabiliteettisakko**: pieni kustannus siitä, että tehtävä vaihtaa kuskia pohjaversioon
   nähden → pieni muutos ei mylläisi koko loppupäivää

## 5. Sijoittamattomien syyanalyysi

Kun ratkaisija pudottaa tehtävän (disjunktio), ajetaan jälkianalyysi:
kokeile tehtävää yksinään jokaista tarjolla olevaa kuskia vasten ja kirjaa
ensimmäinen estävä rajoite.

Syykoodit:
- `aikaikkuna` — kukaan ei ehdi ikkunaan
- `kapasiteetti` — henkilömäärä ei mahdu mihinkään autoon
- `lukituskonflikti` — lukittu kuski ei tarjolla / ei ehdi
- `ei_kuskia` — ei yhtään kuskia tarjolla ko. aikaan

Jokaiseen liitetään ihmisluettava `selite`.

## 6. Ajoaikamatriisi ja välimuisti

- Uusi taulu `matka`: `(mista_lat, mista_lon, mihin_lat, mihin_lon)` pyöristettynä
  4 desimaaliin (≈10 m) → `ajoaika_s`, `matka_m`, `haettu` (timestamp), `lahde`
- Optimoija kysyy ensin välimuistista; puuttuvat parit haetaan reititys-API:sta
  yhtenä matriisikutsuna ja tallennetaan
- Reitityslähde MVP: OSRM (julkinen palvelin) tai OpenRouteService (ilmainen avain).
  Abstrahoi `RouterClient`-rajapinnan taakse → Google Distance Matrix vaihdettavissa.
- Ruuhkat MVP:ssä kertoimella (esim. klo 6–9 noudot ×1,2), ei liikennedataa
- Geokoodaus (osoite → lat/lon) tehdään kun henkilö/lokaatio tallennetaan,
  EI optimoinnin aikana

## 7. Ei MVP:ssä (V2-lista)

- Korjausehdotukset sijoittamattomille ("ota Kalle käyttöön, +88 €")
- Max-paikkojen käyttö hyväksynnällä (epämukava kyyti hätätilanteessa)
- Shuttle-valmiusikkunat (kuski varattuna loop-ajoon aikaikkunassa)
- Viikkosaldo optimointirajoitteena
- Asynkroninen optimointi + pollaus
- Osastoautot hätävarakapasiteettina

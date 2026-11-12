// Tallennetun ajolistaversion kokoaminen samaan muotoon kuin
// POST /paivat/{id}/optimoi -vastaus, jotta Tulos ja Tulostus näyttävät sen
// sellaisenaan. Käytetään, kun Optimointi-välilehti avataan tai sivu
// päivitetään: viimeisin versio näkyy heti ilman uutta laskentaa.
//
// Kaikki tieto tulee olemassa olevista endpointeista (versiot, keikat,
// tehtävät, päivän kuskit, kuskit), joten roolisuodatus on sama kuin niissä.
// Tietokantaan ei tallennu kuskikohtaista lisäkustannusta, sijoittamatta
// jääneiden syitä eikä skenaariovertailua. Ne puuttuvat tästä näkymästä
// (Tulos piilottaa puuttuvat kentät), ja ne saa takaisin optimoimalla uudelleen.
import { haeVersiot, haeKeikat, haeTehtavat, haePaivaKuskit, haeKuskit } from "./api.js";
import { t, hhmm } from "./ui.jsx";

const klo = (aika) => aika.slice(0, 5); // "07:40:00" -> "07:40"

export async function haeTallennettuAjolista(paiva, versioId) {
  const [versiot, keikat, tehtavat, paivaKuskit, kuskit] = await Promise.all([
    haeVersiot(paiva.id),
    haeKeikat(versioId),
    // Passiiviset mukaan: versiossa voi olla keikka tehtävälle tai kuskille,
    // joka on poistettu (soft delete) version luomisen jälkeen.
    haeTehtavat(paiva.id, { sisallaPassiiviset: true }),
    haePaivaKuskit(paiva.id),
    haeKuskit(paiva.tuotanto_id, { sisallaPassiiviset: true }),
  ]);
  const versio = versiot.find((v) => v.id === versioId);
  if (!versio) throw new Error(`Versiota ${versioId} ei löytynyt`);

  const tehtavaById = new Map(tehtavat.map((x) => [x.id, x]));
  const paivaKuskiById = new Map(paivaKuskit.map((x) => [x.id, x]));
  const kuskiById = new Map(kuskit.map((x) => [x.id, x]));

  const perKuski = new Map();
  for (const k of keikat) {
    if (!perKuski.has(k.paiva_kuski_id)) perKuski.set(k.paiva_kuski_id, []);
    perKuski.get(k.paiva_kuski_id).push(k);
  }

  const kuskienAjolistat = [...perKuski.entries()].map(([paivaKuskiId, omat]) => {
    const kuski = kuskiById.get(paivaKuskiById.get(paivaKuskiId)?.kuski_id);
    const jarjestetyt = [...omat].sort((a, b) => t(klo(a.nouto_klo)) - t(klo(b.nouto_klo)));
    // Vuoro ja kesto kuten backendin koosta_kuskien_yhteenveto: ensimmäisestä
    // noudosta viimeiseen jättöön.
    const alku = Math.min(...jarjestetyt.map((k) => t(klo(k.nouto_klo))));
    const loppu = Math.max(...jarjestetyt.map((k) => t(klo(k.jatto_klo))));
    return {
      paiva_kuski_id: paivaKuskiId,
      nimi: kuski?.nimi ?? `Kuski (päiväkuski ${paivaKuskiId})`,
      sopimus: kuski?.sopimus,
      vuoro_alku: hhmm(alku),
      vuoro_loppu: hhmm(loppu),
      kesto_min: loppu - alku,
      lisakustannus_eur: null, // ei tallennu versioon
      keikat: jarjestetyt.map((k) => {
        const teht = tehtavaById.get(k.tehtava_id);
        return {
          keikka_id: k.id,
          tehtava_id: k.tehtava_id,
          nimi: teht?.nimi ?? `Tehtävä ${k.tehtava_id}`,
          nouto_klo: klo(k.nouto_klo),
          jatto_klo: klo(k.jatto_klo),
          mista: teht?.mista_osoite ?? "",
          mihin: teht?.mihin_osoite ?? "",
          kuitattu: k.kuitattu,
          lukittu: k.kuitattu, // kuitattu keikka lukitaan aina reoptimoinnissa
        };
      }),
    };
  });
  kuskienAjolistat.sort((a, b) => t(a.vuoro_alku) - t(b.vuoro_alku));

  // Päivän aktiiviset tehtävät, joita ei ole versiossa. Syy ei tallennu,
  // ja tehtävä on voitu myös lisätä vasta version jälkeen.
  const versiossa = new Set(keikat.map((k) => k.tehtava_id));
  const sijoittamatta = tehtavat
    .filter((x) => x.aktiivinen !== false && !versiossa.has(x.id))
    .map((x) => ({
      tehtava_id: x.id,
      nimi: x.nimi,
      syy: null,
      selite: "ei tässä versiossa (syy näkyy, kun optimoit uudelleen)",
    }));

  return {
    versio_id: versio.id,
    versio_nro: versio.versio_nro,
    kokonaiskustannus_eur: versio.kokonaiskustannus_eur, // KUSKI-roolilla puuttuu
    kuskit: kuskienAjolistat,
    sijoittamatta,
    skenaariot: null,
    tallennettu: { luotu: versio.luotu, julkaistu: versio.julkaistu, tunniste: versio.tunniste },
  };
}

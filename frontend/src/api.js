const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Pyynnön aikaraja: jumiutunut backend näkyy selkeänä virheenä eikä
// ikuisena latauksena tai harhaanjohtavana "ei kuvauspäiviä" -tilana.
const OLETUS_AIKARAJA_MS = 20000;

async function pyyda(polku, options = {}) {
  const { aikarajaMs = OLETUS_AIKARAJA_MS, signal: kutsujanSignal, ...loput } = options;
  const ohjain = new AbortController();
  const ajastin = setTimeout(() => ohjain.abort("aikaraja"), aikarajaMs);
  const peru = () => ohjain.abort(kutsujanSignal.reason);
  kutsujanSignal?.addEventListener("abort", peru);
  let vastaus;
  try {
    vastaus = await fetch(`${API_BASE}${polku}`, {
      headers: { "Content-Type": "application/json" },
      ...loput,
      signal: ohjain.signal,
    });
  } catch (e) {
    if (ohjain.signal.reason === "aikaraja") {
      throw new Error(
        `Backend ei vastannut ${Math.round(aikarajaMs / 1000)} sekunnissa. Onko se käynnissä? (katso AJURI backend -ikkuna)`
      );
    }
    if (e.name === "AbortError") throw e; // kutsuja perui itse (esim. osoitehaku)
    throw new Error("Backendiin ei saatu yhteyttä. Onko se käynnissä? (katso AJURI backend -ikkuna)");
  } finally {
    clearTimeout(ajastin);
    kutsujanSignal?.removeEventListener("abort", peru);
  }
  if (!vastaus.ok) {
    let viesti = `${vastaus.status} ${vastaus.statusText}`;
    try {
      const data = await vastaus.json();
      if (data.detail) viesti = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch {
      // vastauksessa ei ollut JSON-runkoa
    }
    throw new Error(viesti);
  }
  if (vastaus.status === 204) return null; // esim. DELETE, ei runkoa
  return vastaus.json();
}

export function haeKuvauspaivat() {
  return pyyda("/kuvauspaivat");
}

// aikaraja_s pienennetty API:n oletuksesta (15 s), jotta selaindemo pysyy
// ripeänä myös skenaariovertailun neljän ratkaisun summana.
export function optimoiPaiva(paivaId, pyynto = { aikaraja_s: 8 }) {
  return pyyda(`/paivat/${paivaId}/optimoi`, {
    method: "POST",
    body: JSON.stringify(pyynto),
    // ajoaikojen haku OSRM:stä + ratkaisu voi kestää hitaalla yhteydellä
    aikarajaMs: 120000,
  });
}

export function haeTuotannot() {
  return pyyda("/tuotannot");
}

export function haeHenkilot(tuotantoId) {
  return pyyda(`/henkilot?tuotanto_id=${tuotantoId}`);
}
export function luoHenkilo(data) {
  return pyyda("/henkilot", { method: "POST", body: JSON.stringify(data) });
}
export function paivitaHenkilo(id, data) {
  return pyyda(`/henkilot/${id}`, { method: "PUT", body: JSON.stringify(data) });
}
export function poistaHenkilo(id) {
  return pyyda(`/henkilot/${id}`, { method: "DELETE" });
}
export function haeHenkiloKaytto(id) {
  return pyyda(`/henkilot/${id}/kaytto`);
}

export function haeKuskit(tuotantoId, { sisallaPassiiviset = false } = {}) {
  return pyyda(`/kuskit?tuotanto_id=${tuotantoId}${sisallaPassiiviset ? "&sisalla_passiiviset=true" : ""}`);
}
export function luoKuski(data) {
  return pyyda("/kuskit", { method: "POST", body: JSON.stringify(data) });
}
export function paivitaKuski(id, data) {
  return pyyda(`/kuskit/${id}`, { method: "PUT", body: JSON.stringify(data) });
}
export function poistaKuski(id) {
  return pyyda(`/kuskit/${id}`, { method: "DELETE" });
}
export function haeKuskiKaytto(id) {
  return pyyda(`/kuskit/${id}/kaytto`);
}

// --- Pohjatiedot: kuvauspäivät, lokaatiot, ajoneuvot ja päiväkohtaiset rivit ---

const json = (method, data) => ({ method, body: JSON.stringify(data) });

export function haeKuvauspaivatTuotannolle(tuotantoId) {
  return pyyda(`/kuvauspaivat?tuotanto_id=${tuotantoId}`);
}
export function luoKuvauspaiva(data) {
  return pyyda("/kuvauspaivat", json("POST", data));
}
export function paivitaKuvauspaiva(id, data) {
  return pyyda(`/kuvauspaivat/${id}`, json("PUT", data));
}

export function haeLokaatiot(tuotantoId) {
  return pyyda(`/lokaatiot?tuotanto_id=${tuotantoId}`);
}
export function luoLokaatio(data) {
  return pyyda("/lokaatiot", json("POST", data));
}

export function haeAjoneuvot(tuotantoId) {
  return pyyda(`/ajoneuvot?tuotanto_id=${tuotantoId}`);
}

export function haePaivaLokaatiot(paivaId) {
  return pyyda(`/paiva-lokaatiot?paiva_id=${paivaId}`);
}
export function luoPaivaLokaatio(data) {
  return pyyda("/paiva-lokaatiot", json("POST", data));
}
export function paivitaPaivaLokaatio(id, data) {
  return pyyda(`/paiva-lokaatiot/${id}`, json("PUT", data));
}
export function poistaPaivaLokaatio(id) {
  return pyyda(`/paiva-lokaatiot/${id}`, { method: "DELETE" });
}

export function haePaivaHenkilot(paivaId) {
  return pyyda(`/paiva-henkilot?paiva_id=${paivaId}`);
}
export function luoPaivaHenkilo(data) {
  return pyyda("/paiva-henkilot", json("POST", data));
}
export function paivitaPaivaHenkilo(id, data) {
  return pyyda(`/paiva-henkilot/${id}`, json("PUT", data));
}
export function poistaPaivaHenkilo(id) {
  return pyyda(`/paiva-henkilot/${id}`, { method: "DELETE" });
}

export function haePaivaKuskit(paivaId) {
  return pyyda(`/paiva-kuskit?paiva_id=${paivaId}`);
}
export function luoPaivaKuski(data) {
  return pyyda("/paiva-kuskit", json("POST", data));
}
export function paivitaPaivaKuski(id, data) {
  return pyyda(`/paiva-kuskit/${id}`, json("PUT", data));
}
export function poistaPaivaKuski(id) {
  return pyyda(`/paiva-kuskit/${id}`, { method: "DELETE" });
}

// --- Tehtävät: generointi ja käsin lisätyt ---

export function haeTehtavat(paivaId, { sisallaPassiiviset = false } = {}) {
  return pyyda(`/tehtavat?paiva_id=${paivaId}${sisallaPassiiviset ? "&sisalla_passiiviset=true" : ""}`);
}
export function luoTehtava(data) {
  return pyyda("/tehtavat", json("POST", data));
}
export function paivitaTehtava(id, data) {
  return pyyda(`/tehtavat/${id}`, json("PUT", data));
}
export function poistaTehtava(id) {
  return pyyda(`/tehtavat/${id}`, { method: "DELETE" });
}
// Vastaus: { tehtavat: [...], varoitus: string | null }
export function generoiTehtavat(paivaId) {
  return pyyda(`/paivat/${paivaId}/generoi-tehtavat`, { method: "POST" });
}

// --- Osoite-ehdotukset (Photon backendin kautta) ---

export function ehdotaOsoitteita(q, signal) {
  return pyyda(`/osoitteet/ehdota?q=${encodeURIComponent(q)}`, { signal });
}

// --- Ajolistaversiot ja niiden vertailu ---

export function haeVersiot(paivaId) {
  return pyyda(`/versiot?paiva_id=${paivaId}`);
}
export function haeKeikat(versioId) {
  return pyyda(`/keikat?versio_id=${versioId}`);
}
// Vastaus: { paiva_id, kaynnissa, viimeisin_versio_id }. Kevyt, kysellään
// muutaman sekunnin välein, kun laskenta on kesken.
export function haeOptimoinninTila(paivaId) {
  return pyyda(`/paivat/${paivaId}/optimointi`);
}
// a = vanha, b = uusi. KUSKI-roolilla kustannuskentät puuttuvat vastauksesta.
export function haeVersiodiff(aId, bId) {
  return pyyda(`/versiot/${aId}/diff/${bId}`);
}

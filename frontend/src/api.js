const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function pyyda(polku, options) {
  const vastaus = await fetch(`${API_BASE}${polku}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!vastaus.ok) {
    let viesti = `${vastaus.status} ${vastaus.statusText}`;
    try {
      const data = await vastaus.json();
      if (data.detail) viesti = data.detail;
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

export function haeKuskit(tuotantoId) {
  return pyyda(`/kuskit?tuotanto_id=${tuotantoId}`);
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

// --- Osoite-ehdotukset (Photon backendin kautta) ---

export function ehdotaOsoitteita(q, signal) {
  return pyyda(`/osoitteet/ehdota?q=${encodeURIComponent(q)}`, { signal });
}

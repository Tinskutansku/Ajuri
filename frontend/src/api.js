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

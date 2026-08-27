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

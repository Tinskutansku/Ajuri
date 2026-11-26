import { useEffect, useState } from "react";
import { C, FONTS, Nappi } from "./ui.jsx";
import { haeMina } from "./api.js";
import {
  ROOLI_NIMI,
  asetaVanhenemisKasittelija,
  haeIstunto,
  paivitaKayttaja,
  tyhjennaIstunto,
  voiMuokata,
} from "./istunto.js";
import Kirjautuminen from "./Kirjautuminen.jsx";
import Rekisteri from "./Rekisteri.jsx";
import Pohjatiedot from "./Pohjatiedot.jsx";
import Tehtavat from "./Tehtavat.jsx";
import Optimointi from "./Optimointi.jsx";
import KuskinPaiva from "./KuskinPaiva.jsx";

const TABS = [
  ["rekisteri", "☰ Rekisteri"],
  ["pohjatiedot", "◆ Pohjatiedot"],
  ["tehtavat", "▲ Tehtävät"],
  ["optimointi", "★ Optimointi"],
];

// KUSKI saa vain lukea. Kuski ei näe välilehtiä lainkaan, vaan oman
// päivänsä puhelimelle suunnitellussa näkymässä (KuskinPaiva, ROADMAP N2).
// Backend estää muokkaukset joka tapauksessa (403).

export default function App() {
  const [kayttaja, setKayttaja] = useState(() => haeIstunto()?.kayttaja ?? null);
  const [ilmoitus, setIlmoitus] = useState(null);
  const [tab, setTab] = useState(() => (voiMuokata(haeIstunto()?.kayttaja) ? "rekisteri" : "optimointi"));

  // Mikä tahansa 401 tokenin kanssa (api.js) palauttaa kirjautumissivulle.
  useEffect(() => {
    asetaVanhenemisKasittelija(() => {
      setKayttaja(null);
      setIlmoitus("Istunto vanheni. Kirjaudu uudelleen.");
    });
    return () => asetaVanhenemisKasittelija(null);
  }, []);

  // Sivun päivityksen jälkeen tarkistetaan, että tallennettu token kelpaa
  // yhä, ja päivitetään nimi ja rooli backendistä.
  useEffect(() => {
    if (!haeIstunto()) return;
    haeMina()
      .then((k) => {
        paivitaKayttaja(k);
        setKayttaja(k);
      })
      .catch(() => {
        // 401 hoidetaan vanhenemiskäsittelijässä; verkkovirhe näkyy välilehdillä
      });
  }, []);

  const kirjautunut = (k) => {
    setIlmoitus(null);
    setTab(voiMuokata(k) ? "rekisteri" : "optimointi");
    setKayttaja(k);
  };

  const kirjauduUlos = () => {
    tyhjennaIstunto();
    setKayttaja(null);
    setIlmoitus("Kirjauduit ulos.");
  };

  const muokkaaja = voiMuokata(kayttaja);

  return (
    <div style={{ minHeight: "100vh", background: C.paper, color: C.inkSolid, paddingBottom: 80 }}>
      <style>{FONTS}</style>

      <header style={{ borderBottom: `3px solid ${C.line}`, background: C.paper }}>
        <div style={{ height: 10, display: "flex" }}>
          {[C.rust, C.orange, C.ochre, C.olive, C.teal].map((c) => (
            <div key={c} style={{ flex: 1, background: c }} />
          ))}
        </div>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "22px 20px 14px", display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <h1 style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: "clamp(34px, 7vw, 52px)", margin: 0, letterSpacing: "-0.02em", lineHeight: 0.95 }}>
            AJO<span style={{ color: C.orange }}>LISTA</span>
          </h1>
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, fontWeight: 600, color: C.olive }}>
            demo
          </span>
          {kayttaja && (
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, fontWeight: 600, color: C.inkSolid }}>
                {kayttaja.nimi}
                <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: C.olive, marginLeft: 8 }}>
                  {ROOLI_NIMI[kayttaja.rooli] ?? kayttaja.rooli}
                </span>
              </span>
              <Nappi variant="ghost" onClick={kirjauduUlos} style={{ fontSize: 12, padding: "6px 14px" }}>
                Kirjaudu ulos
              </Nappi>
            </div>
          )}
        </div>
      </header>

      {!kayttaja && (
        <main style={{ maxWidth: 900, margin: "0 auto", padding: "28px 16px 0" }}>
          <Kirjautuminen onKirjautunut={kirjautunut} ilmoitus={ilmoitus} />
        </main>
      )}

      {kayttaja && !muokkaaja && (
        <main style={{ maxWidth: 900, margin: "0 auto", padding: "16px 14px 0" }}>
          <KuskinPaiva />
        </main>
      )}

      {kayttaja && muokkaaja && (
        <main style={{ maxWidth: 900, margin: "0 auto", padding: "20px 20px 0" }}>
          <nav style={{ display: "flex", gap: 8, marginBottom: 22, flexWrap: "wrap" }}>
            {TABS.map(([k, nimi]) => (
              <button
                key={k}
                onClick={() => setTab(k)}
                style={{
                  fontFamily: "'Archivo',sans-serif",
                  fontWeight: 700,
                  fontSize: 13,
                  cursor: "pointer",
                  padding: "8px 16px",
                  borderRadius: 999,
                  border: `2px solid ${C.line}`,
                  background: tab === k ? C.inkSolid : C.card,
                  color: tab === k ? C.card : C.inkSolid,
                  boxShadow: tab === k ? `3px 3px 0 ${C.orange}` : "none",
                }}
              >
                {nimi}
              </button>
            ))}
          </nav>

          {tab === "rekisteri" && <Rekisteri />}
          {tab === "pohjatiedot" && <Pohjatiedot />}
          {tab === "tehtavat" && <Tehtavat />}
          {tab === "optimointi" && <Optimointi voiMuokata={muokkaaja} />}
        </main>
      )}
    </div>
  );
}

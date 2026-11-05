import { useState } from "react";
import { C, FONTS } from "./ui.jsx";
import Rekisteri from "./Rekisteri.jsx";
import Pohjatiedot from "./Pohjatiedot.jsx";
import Optimointi from "./Optimointi.jsx";

const TABS = [
  ["rekisteri", "☰ Rekisteri"],
  ["pohjatiedot", "◆ Pohjatiedot"],
  ["optimointi", "★ Optimointi"],
];

export default function App() {
  const [tab, setTab] = useState("rekisteri");

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
        </div>
      </header>

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
        {tab === "optimointi" && <Optimointi />}
      </main>
    </div>
  );
}

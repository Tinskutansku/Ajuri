import { useEffect, useState } from "react";
import { haeVersiot, haeVersiodiff } from "./api.js";
import { C, Kortti, Badge, pikkuLabel, riviTyyli, vihje } from "./ui.jsx";

// "Mitä muuttui" -näkymä: vertaa kahta saman päivän ajolistaversiota
// (GET /versiot/{a}/diff/{b}). Oletuksena uusin versio vs. sitä edellinen.

// Badgen teksti on tummaa, joten taustan pitää olla vaalea (kontrasti).
const VAALEA_VIHREA = "#CFE3DC";
const VAALEA_PUNAINEN = "#F7DFD2";

const klo = (s) => (s ? s.slice(0, 5) : "–");
const mono = { fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, fontSize: 13 };
const teksti = { fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.inkSolid };

function versioNimi(v) {
  const aika = new Date(v.luotu).toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit" });
  return `v${v.versio_nro}${v.tunniste ? ` ${v.tunniste}` : ""} · ${aika}${v.julkaistu ? " · julkaistu" : ""}`;
}

function ajat(nouto, jatto) {
  return `${klo(nouto)}–${klo(jatto)}`;
}

function Rivi({ badge, vari, nimi, children }) {
  return (
    <div style={{ ...riviTyyli, padding: "6px 0", flexWrap: "wrap", gap: 8 }}>
      <Badge color={vari}>{badge}</Badge>
      <span style={{ ...teksti, fontWeight: 700 }}>{nimi}:</span>
      <span style={teksti}>{children}</span>
    </div>
  );
}

function ValitseVersio({ label, arvo, versiot, onChange }) {
  return (
    <label>
      <div style={pikkuLabel}>{label}</div>
      <select
        value={arvo}
        onChange={(e) => onChange(e.target.value)}
        style={{
          ...mono,
          padding: "8px 10px",
          border: `2px solid ${C.line}`,
          borderRadius: 8,
          background: C.card,
          color: C.inkSolid,
          cursor: "pointer",
        }}
      >
        {versiot.map((v) => (
          <option key={v.id} value={v.id}>
            {versioNimi(v)}
          </option>
        ))}
      </select>
    </label>
  );
}

function euroMuutos(eur) {
  const pyoristetty = Math.round(eur);
  if (pyoristetty === 0) return "±0 €";
  return `${pyoristetty > 0 ? "+" : "−"}${Math.abs(pyoristetty)} €`;
}

export default function Versiodiff({ paivaId, nykyinenVersioId }) {
  const [versiot, setVersiot] = useState([]);
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [diff, setDiff] = useState(null);
  const [virhe, setVirhe] = useState(null);

  // Versiolista haetaan uudelleen kun päivä vaihtuu tai optimointi tuottaa
  // uuden version. Oletus: uusin (tai juuri laskettu) vs. sitä edellinen.
  useEffect(() => {
    if (!paivaId) return;
    let peruttu = false;
    setVirhe(null);
    setDiff(null);
    haeVersiot(paivaId)
      .then((lista) => {
        if (peruttu) return;
        const jarj = [...lista].sort((x, y) => x.versio_nro - y.versio_nro);
        setVersiot(jarj);
        let bi = jarj.findIndex((v) => v.id === nykyinenVersioId);
        if (bi < 0) bi = jarj.length - 1;
        setBId(bi >= 0 ? String(jarj[bi].id) : "");
        setAId(bi > 0 ? String(jarj[bi - 1].id) : "");
      })
      .catch((e) => !peruttu && setVirhe(e.message));
    return () => {
      peruttu = true;
    };
  }, [paivaId, nykyinenVersioId]);

  useEffect(() => {
    if (!aId || !bId || aId === bId) {
      setDiff(null);
      return;
    }
    let peruttu = false;
    setVirhe(null);
    haeVersiodiff(aId, bId)
      .then((d) => !peruttu && setDiff(d))
      .catch((e) => !peruttu && setVirhe(e.message));
    return () => {
      peruttu = true;
    };
  }, [aId, bId]);

  if (!paivaId) return null;
  if (versiot.length < 2 && !virhe) {
    // Ei vielä vertailtavaa: korttia ei näytetä turhaan.
    return null;
  }

  const muutoksia =
    diff &&
    diff.siirtyneet.length + diff.kuskia_vaihtaneet.length + diff.uudet.length + diff.poistuneet.length;

  // Kustannuskentät puuttuvat KUSKI-roolin vastauksesta kokonaan.
  const naytaKustannus = diff && diff.kustannusmuutos_eur != null;

  return (
    <Kortti
      otsikko="Mitä muuttui"
      nro="Δ"
      lisa={naytaKustannus ? `kustannus ${euroMuutos(diff.kustannusmuutos_eur)}` : undefined}
    >
      {virhe && (
        <p style={{ ...teksti, color: C.rust, fontWeight: 600 }}>Versioiden vertailu epäonnistui: {virhe}</p>
      )}

      {versiot.length >= 2 && (
        <div style={{ display: "flex", gap: 14, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 12 }}>
          <ValitseVersio label="Vanha versio" arvo={aId} versiot={versiot} onChange={setAId} />
          <span style={{ ...mono, paddingBottom: 10 }}>→</span>
          <ValitseVersio label="Uusi versio" arvo={bId} versiot={versiot} onChange={setBId} />
        </div>
      )}

      {aId && aId === bId && <p style={vihje}>Valitse kaksi eri versiota.</p>}

      {diff && (
        <>
          {diff.kuskit.length > 0 && (
            <p style={{ ...teksti, fontWeight: 600, margin: "0 0 8px" }}>
              {diff.kuskit
                .map((k) => `${k.kuski_nimi} ${k.muutos > 0 ? "+" : "−"}${Math.abs(k.muutos)} keikka${Math.abs(k.muutos) === 1 ? "" : "a"}`)
                .join(" · ")}
            </p>
          )}

          {diff.siirtyneet.map((d) => (
            <Rivi key={`s${d.tehtava_id}`} badge="aika" vari={C.ochre} nimi={d.tehtava_nimi}>
              {[
                d.nouto_klo_a !== d.nouto_klo_b && (
                  <span key="n">
                    nouto <b style={mono}>{klo(d.nouto_klo_a)} → {klo(d.nouto_klo_b)}</b>
                  </span>
                ),
                d.jatto_klo_a !== d.jatto_klo_b && (
                  <span key="j">
                    jättö <b style={mono}>{klo(d.jatto_klo_a)} → {klo(d.jatto_klo_b)}</b>
                  </span>
                ),
              ]
                .filter(Boolean)
                .reduce((acc, el, i) => (i ? [...acc, " · ", el] : [el]), [])}
            </Rivi>
          ))}

          {diff.kuskia_vaihtaneet.map((d) => (
            <Rivi key={`k${d.tehtava_id}`} badge="kuski" vari={C.orange} nimi={d.tehtava_nimi}>
              {d.kuski_nimi_a} → <b>{d.kuski_nimi_b}</b>
            </Rivi>
          ))}

          {diff.uudet.map((d) => (
            <Rivi key={`u${d.tehtava_id}`} badge="uusi" vari={VAALEA_VIHREA} nimi={d.tehtava_nimi}>
              <span style={mono}>{ajat(d.nouto_klo_b, d.jatto_klo_b)}</span> · {d.kuski_nimi_b}
            </Rivi>
          ))}

          {diff.poistuneet.map((d) => (
            <Rivi key={`p${d.tehtava_id}`} badge="poistui" vari={VAALEA_PUNAINEN} nimi={d.tehtava_nimi}>
              <s style={mono}>{ajat(d.nouto_klo_a, d.jatto_klo_a)}</s> · oli {d.kuski_nimi_a}
            </Rivi>
          ))}

          <p style={vihje}>
            {muutoksia === 0 ? "Ei muutoksia keikoissa. " : ""}
            {diff.ennallaan_lkm} {diff.ennallaan_lkm === 1 ? "keikka" : "keikkaa"} ennallaan.
          </p>
        </>
      )}
    </Kortti>
  );
}

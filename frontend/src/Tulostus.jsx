/* Ajolistan tulostusversio (ROADMAP I1).

   Tulostettava sivu renderöidään portaalilla suoraan <body>:n alle, jotta
   index.css:n @media print voi piilottaa koko muun sovelluksen (#root)
   ja näyttää vain tämän. Ruudulla tuloste on piilossa.

   Tulosteeseen EI tule yhtään kustannusta: optimointivastauksesta
   käytetään vain aikoja, nimiä ja osoitteita. Yhteystiedot (puhelin,
   auto, tehtävän huomiot) haetaan olemassa olevista endpointeista. */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { haeAjoneuvot, haeHenkilot, haeKuskit, haePaivaKuskit, haeTehtavat } from "./api.js";
import { C, Nappi, vihje } from "./ui.jsx";

const VIIKONPAIVAT = ["su", "ma", "ti", "ke", "to", "pe", "la"];

function muotoilePvm(iso) {
  const [v, k, p] = iso.split("-").map(Number);
  const vp = VIIKONPAIVAT[new Date(v, k - 1, p).getDay()];
  return `${vp} ${p}.${k}.${v}`;
}

const lyhytAika = (s) => (s ? s.slice(0, 5) : "");

// Yhteystiedot hakuineen. Jos jokin haku epäonnistuu, tuloste toimii
// silti ilman puhelinnumeroita, ja virhe näytetään napin vieressä.
function useYhteystiedot(paiva) {
  const [tiedot, setTiedot] = useState(null);
  const [virhe, setVirhe] = useState(null);

  useEffect(() => {
    if (!paiva) return;
    // Päivän vaihto nollaa tuloksen Optimointi.jsx:ssä, jolloin tämä
    // komponentti purkautuu, joten tilaa ei tarvitse nollata tässä.
    let peruttu = false;
    Promise.all([
      haePaivaKuskit(paiva.id),
      haeKuskit(paiva.tuotanto_id),
      haeAjoneuvot(paiva.tuotanto_id),
      haeTehtavat(paiva.id),
      haeHenkilot(paiva.tuotanto_id),
    ])
      .then(([paivaKuskit, kuskit, ajoneuvot, tehtavat, henkilot]) => {
        if (peruttu) return;
        const kuskiById = new Map(kuskit.map((k) => [k.id, k]));
        const autoById = new Map(ajoneuvot.map((a) => [a.id, a]));
        const henkiloById = new Map(henkilot.map((h) => [h.id, h]));

        const paivaKuski = new Map(
          paivaKuskit.map((pk) => {
            const auto = autoById.get(pk.ajoneuvo_id);
            return [
              pk.id,
              {
                puhelin: kuskiById.get(pk.kuski_id)?.puhelin ?? null,
                auto: auto ? [auto.nimi, auto.rekisteri].filter(Boolean).join(" ") : null,
              },
            ];
          })
        );
        const tehtava = new Map(
          tehtavat.map((tt) => [
            tt.id,
            {
              puhelin: henkiloById.get(tt.henkilo_id)?.puhelin ?? null,
              henkiloita: tt.henkiloita,
              huomiot: tt.huomiot,
            },
          ])
        );
        setTiedot({ paivaKuski, tehtava });
      })
      .catch((e) => !peruttu && setVirhe(e.message));
    return () => {
      peruttu = true;
    };
  }, [paiva]);

  return { tiedot, virhe };
}

const solu = { border: "1px solid #999", padding: "4px 6px", verticalAlign: "top", textAlign: "left" };
const otsikkoSolu = { ...solu, background: "#eee", fontWeight: 700, fontSize: 10, textTransform: "uppercase" };

function TulosteenKuski({ kuski, yt }) {
  const pk = yt?.paivaKuski.get(kuski.paiva_kuski_id);
  return (
    <section className="tuloste-kuski">
      <h2 style={{ fontSize: 15, margin: "14px 0 4px" }}>
        {kuski.nimi}
        {pk?.puhelin && <span style={{ fontWeight: 400 }}> · {pk.puhelin}</span>}
      </h2>
      <div style={{ fontSize: 11, marginBottom: 4 }}>
        Vuoro {kuski.vuoro_alku}–{kuski.vuoro_loppu}
        {pk?.auto ? ` · auto ${pk.auto}` : ""} · {kuski.keikat.length} {kuski.keikat.length === 1 ? "keikka" : "keikkaa"}
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11 }}>
        <thead>
          <tr>
            <th style={{ ...otsikkoSolu, width: 78 }}>Aika</th>
            <th style={otsikkoSolu}>Kyyti</th>
            <th style={{ ...otsikkoSolu, width: 100 }}>Puhelin</th>
            <th style={otsikkoSolu}>Mistä → mihin</th>
            <th style={otsikkoSolu}>Huom.</th>
          </tr>
        </thead>
        <tbody>
          {kuski.keikat.map((k) => {
            const tt = yt?.tehtava.get(k.tehtava_id);
            return (
              <tr key={k.keikka_id}>
                <td style={{ ...solu, fontFamily: "monospace", whiteSpace: "nowrap" }}>
                  {k.nouto_klo}–{k.jatto_klo}
                </td>
                <td style={solu}>
                  {k.nimi}
                  {tt && tt.henkiloita > 1 ? ` (${tt.henkiloita} hlö)` : ""}
                  {tt && tt.henkiloita === 0 ? " (tavara)" : ""}
                </td>
                <td style={{ ...solu, whiteSpace: "nowrap" }}>{tt?.puhelin ?? ""}</td>
                <td style={solu}>
                  {k.mista} → {k.mihin}
                </td>
                <td style={solu}>
                  {[k.lukittu ? "lukittu" : null, tt?.huomiot].filter(Boolean).join(" · ")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function Tuloste({ tulos, paiva, yt }) {
  return (
    <div className="tuloste" style={{ fontFamily: "Arial, Helvetica, sans-serif", color: "#000" }}>
      <h1 style={{ fontSize: 20, margin: "0 0 2px" }}>
        Ajolista {muotoilePvm(paiva.pvm)}
        {paiva.paiva_nro ? ` · päivä ${paiva.paiva_nro}` : ""}
      </h1>
      <div style={{ fontSize: 11, marginBottom: 6 }}>
        Call {lyhytAika(paiva.call_time)}
        {paiva.lounas ? ` · lounas ${lyhytAika(paiva.lounas)}` : ""}
        {paiva.wrap_arvio ? ` · wrap n. ${lyhytAika(paiva.wrap_arvio)}` : ""}
        {` · versio ${tulos.versio_nro} · ${tulos.kuskit.length} kuskia`}
      </div>
      {paiva.huomiot && <div style={{ fontSize: 11, marginBottom: 6 }}>Huom: {paiva.huomiot}</div>}

      {tulos.kuskit.map((k) => (
        <TulosteenKuski key={k.paiva_kuski_id} kuski={k} yt={yt} />
      ))}

      {!!tulos.sijoittamatta.length && (
        <section className="tuloste-kuski">
          <h2 style={{ fontSize: 13, margin: "14px 0 4px" }}>Ilman kuskia ({tulos.sijoittamatta.length})</h2>
          <div style={{ fontSize: 11 }}>{tulos.sijoittamatta.map((s) => s.nimi).join(" · ")}</div>
        </section>
      )}
    </div>
  );
}

export default function Tulostus({ tulos, paiva }) {
  const { tiedot, virhe } = useYhteystiedot(paiva);
  if (!paiva) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 18 }}>
      <Nappi onClick={() => window.print()} disabled={!tiedot && !virhe}>
        {tiedot || virhe ? "🖨 Tulosta ajolista" : "Haetaan yhteystietoja…"}
      </Nappi>
      {virhe ? (
        <span style={{ ...vihje, marginTop: 0, color: C.rust }}>
          Yhteystietojen haku epäonnistui ({virhe}), tuloste ilman puhelinnumeroita.
        </span>
      ) : (
        <span style={{ ...vihje, marginTop: 0 }}>A4, ilman kustannuksia, puhelinnumerot mukana.</span>
      )}
      {createPortal(<Tuloste tulos={tulos} paiva={paiva} yt={tiedot} />, document.body)}
    </div>
  );
}

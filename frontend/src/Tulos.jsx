import { C, Kortti, Badge, riviTyyli, vihje, t, hhmm, SOPIMUS_NIMI } from "./ui.jsx";

const YLITYO_RAJA_MIN = 8 * 60;

function Aikajana({ keikat, MIN, W }) {
  const tunnit = [];
  for (let h = Math.ceil(MIN / 60); h * 60 <= MIN + W; h += 2) tunnit.push(h);

  return (
    <div
      style={{
        position: "relative",
        height: 34,
        background: C.paper,
        border: `2px solid ${C.line}`,
        borderRadius: 8,
        marginBottom: 12,
        overflow: "hidden",
      }}
    >
      {tunnit.map((h) => (
        <div
          key={h}
          style={{
            position: "absolute",
            left: `${((h * 60 - MIN) / W) * 100}%`,
            top: 0,
            bottom: 0,
            borderLeft: `1px dashed ${C.ink}`,
            fontSize: 9,
            fontFamily: "'IBM Plex Mono',monospace",
            paddingLeft: 2,
          }}
        >
          {h}
        </div>
      ))}
      {keikat.map((k, j) => {
        const nouto = t(k.nouto_klo);
        const jatto = t(k.jatto_klo);
        return (
          <div
            key={j}
            title={`${k.nimi} ${k.nouto_klo}–${k.jatto_klo}`}
            style={{
              position: "absolute",
              top: 6,
              height: 18,
              borderRadius: 6,
              border: `2px solid ${C.line}`,
              background: k.lukittu ? C.teal : C.orange,
              left: `${((nouto - MIN) / W) * 100}%`,
              width: `${Math.max(1.2, ((jatto - nouto) / W) * 100)}%`,
            }}
          />
        );
      })}
    </div>
  );
}

function KuskinKortti({ kuski, nro, MIN, W }) {
  const ylitoita = kuski.kesto_min > YLITYO_RAJA_MIN;
  const lisa =
    `${kuski.vuoro_alku}–${kuski.vuoro_loppu} · ` +
    `${Math.floor(kuski.kesto_min / 60)}h ${String(kuski.kesto_min % 60).padStart(2, "0")}min · ` +
    `${SOPIMUS_NIMI[kuski.sopimus] ?? kuski.sopimus} · ` +
    `+${Math.round(kuski.lisakustannus_eur)} €` +
    (ylitoita ? " · YLITYÖTÄ" : "");

  return (
    <Kortti otsikko={kuski.nimi} nro={String(nro)} lisa={lisa}>
      <Aikajana keikat={kuski.keikat} MIN={MIN} W={W} />
      {kuski.keikat.map((k, j) => (
        <div key={j} style={{ ...riviTyyli, padding: "5px 0" }}>
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, fontSize: 13, width: 96 }}>
            {k.nouto_klo}–{k.jatto_klo}
          </span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: 99,
              background: k.lukittu ? C.teal : C.orange,
              flexShrink: 0,
            }}
          />
          <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 13 }}>{k.nimi}</span>
          {k.lukittu && <Badge color={C.teal}>LUKITTU</Badge>}
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive, marginLeft: "auto" }}>
            {k.mista} → {k.mihin}
          </span>
        </div>
      ))}
    </Kortti>
  );
}

function Sijoittamattomat({ sijoittamatta }) {
  if (!sijoittamatta.length) return null;
  return (
    <div
      style={{
        border: `2px solid ${C.rust}`,
        background: "#F7DFD2",
        borderRadius: 12,
        padding: "12px 16px",
        marginBottom: 16,
      }}
    >
      <div style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 13, color: C.rust, marginBottom: 6 }}>
        ⚠ Sijoittamatta jäi {sijoittamatta.length} tehtävää
      </div>
      {sijoittamatta.map((s) => (
        <div key={s.tehtava_id} style={{ fontFamily: "'Archivo',sans-serif", fontSize: 12, color: C.inkSolid, marginBottom: 2 }}>
          <b>{s.nimi}</b>{" "}
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 10, color: C.rust }}>[{s.syy}]</span> — {s.selite}
        </div>
      ))}
    </div>
  );
}

function Skenaariot({ skenaariot }) {
  if (!skenaariot) return null;
  return (
    <Kortti otsikko="Montako kuskia kannattaa ottaa?" nro="€">
      {skenaariot.map((s) => (
        <div
          key={s.kuskeja_tarjolla}
          style={{ ...riviTyyli, fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600 }}
        >
          <span>
            {s.kuskeja_tarjolla} tarjolla → {s.kuskeja_kaytossa} käytössä
          </span>
          <span style={{ marginLeft: "auto", fontWeight: 700, color: s.halvin ? C.orange : C.inkSolid }}>
            {s.ratkeaa ? `${Math.round(s.kustannus_eur)} €` : "ei ratkea"}
            {s.halvin ? "  ★ halvin" : ""}
          </span>
        </div>
      ))}
      <p style={vihje}>Sopimus-ensin-järjestys: kk-sopimus- ja päiväpalkkakuskit otetaan käyttöön ennen extroja.</p>
    </Kortti>
  );
}

export default function Tulos({ tulos }) {
  const kaikkiAjat = tulos.kuskit.flatMap((k) => k.keikat.flatMap((kk) => [t(kk.nouto_klo), t(kk.jatto_klo)]));
  const MIN = kaikkiAjat.length ? Math.max(0, Math.floor(Math.min(...kaikkiAjat) / 60) * 60 - 30) : 6 * 60;
  const MAX = kaikkiAjat.length ? Math.ceil(Math.max(...kaikkiAjat) / 60) * 60 + 30 : 21 * 60;
  const W = MAX - MIN;

  return (
    <div>
      <div style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: 30, marginBottom: 4 }}>
        +{Math.round(tulos.kokonaiskustannus_eur)} €
        <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 12, marginLeft: 10, color: C.olive }}>
          päivän lisäkustannus · {tulos.kuskit.length} kuskia käytössä
        </span>
      </div>
      <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive, marginBottom: 18 }}>
        versio {tulos.versio_nro} (id {tulos.versio_id})
      </div>

      <Sijoittamattomat sijoittamatta={tulos.sijoittamatta} />

      {tulos.kuskit.map((k, i) => (
        <KuskinKortti key={k.paiva_kuski_id} kuski={k} nro={i + 1} MIN={MIN} W={W} />
      ))}

      <Skenaariot skenaariot={tulos.skenaariot} />
    </div>
  );
}

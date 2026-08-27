/* Design-tokenit ja pienet jaetut komponentit — tyyli ja komponenttirakenne
   poimittu docs/ajolista_ui_luonnos_v2.jsx:stä. */

export const C = {
  paper: "#F4EBD7",
  card: "#FBF5E6",
  ink: "#33241691",
  inkSolid: "#332416",
  orange: "#DE6A1F",
  ochre: "#D9A32B",
  olive: "#77762F",
  teal: "#3F6F68",
  rust: "#B04327",
  line: "#332416",
};

export const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700;9..144,900&family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
`;

// "HH:MM" -> minuutteja keskiyöstä, ja takaisin.
export const t = (s) => {
  const [h, m] = s.split(":").map(Number);
  return h * 60 + (m || 0);
};
export const hhmm = (m) =>
  `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

export const SOPIMUS_NIMI = {
  kuukausi: "kk-sopimus",
  paiva: "päiväpalkka",
  tunti: "extra/tunti",
};

export const pikkuLabel = {
  fontFamily: "'Archivo',sans-serif",
  fontSize: 10,
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.08em",
  color: C.olive,
  marginBottom: 3,
};

export const vihje = {
  fontFamily: "'Archivo',sans-serif",
  fontSize: 11,
  color: C.olive,
  fontWeight: 500,
  marginTop: 10,
  marginBottom: 0,
};

export const riviTyyli = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  padding: "8px 0",
  borderBottom: `1px solid ${C.ink}`,
  color: C.inkSolid,
};

export function Nappi({ children, onClick, variant = "ink", disabled = false, style = {} }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "'Archivo',sans-serif",
        fontWeight: 700,
        fontSize: 14,
        padding: "10px 18px",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        borderRadius: 999,
        border: `2px solid ${C.line}`,
        background: variant === "orange" ? C.orange : variant === "ghost" ? "transparent" : C.inkSolid,
        color: variant === "ghost" ? C.inkSolid : C.card,
        boxShadow: variant === "ghost" ? "none" : `3px 3px 0 ${C.line}`,
        ...style,
      }}
    >
      {children}
    </button>
  );
}

export function Kortti({ otsikko, nro, lisa, children }) {
  return (
    <section
      style={{
        background: C.card,
        border: `2px solid ${C.line}`,
        borderRadius: 16,
        boxShadow: `5px 5px 0 ${C.line}`,
        padding: "18px 20px",
        marginBottom: 22,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
        <span
          style={{
            fontFamily: "'Fraunces',serif",
            fontWeight: 900,
            fontSize: 15,
            width: 28,
            height: 28,
            borderRadius: 99,
            background: C.inkSolid,
            color: C.card,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            alignSelf: "center",
          }}
        >
          {nro}
        </span>
        <h2 style={{ fontFamily: "'Fraunces',serif", fontWeight: 700, fontSize: 20, margin: 0, color: C.inkSolid }}>
          {otsikko}
        </h2>
        {lisa && (
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, fontWeight: 600, color: C.rust, marginLeft: "auto" }}>
            {lisa}
          </span>
        )}
      </div>
      {children}
    </section>
  );
}

export function Badge({ children, color = C.ochre }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontFamily: "'Archivo',sans-serif",
        fontWeight: 700,
        background: color,
        border: `2px solid ${C.line}`,
        borderRadius: 99,
        padding: "1px 8px",
        color: C.inkSolid,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

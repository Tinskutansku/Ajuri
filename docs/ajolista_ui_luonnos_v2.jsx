import { useState, useRef } from "react";
import * as XLSX from "xlsx";

/* =========================================================================
   AJOLISTA v2 — klikkailtava UI-luonnos
   Välilehdet: Rekisteri · 1 Pohjatiedot · 2 Tehtävät · 3 Ajolista
   Ajolistassa kaksi näkymää: Suunnittelu (€) ja Tulostus (ei €).
   Demo-optimointi selaimessa; tuotannossa OR-Tools/FastAPI.
   ========================================================================= */

// ---------- design tokens ----------
const C = {
  paper: "#F4EBD7", card: "#FBF5E6", ink: "#33241691", inkSolid: "#332416",
  orange: "#DE6A1F", ochre: "#D9A32B", olive: "#77762F", teal: "#3F6F68", rust: "#B04327", line: "#332416",
};
const FONTS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700;9..144,900&family=Archivo:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
@media print {
  .ei-printtiin { display: none !important; }
  body { background: #fff !important; }
}
`;

// ---------- apuja ----------
const t = (s) => { const [h, m] = s.split(":").map(Number); return h * 60 + (m || 0); };
const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

const PAIKAT = {
  LOC1: [10, 10], LOC2: [16, 12],
  "Hotelli A": [4, 8], "Hotelli B": [5.5, 6.5],
  "Museokuja 8": [14, 4], "Rantapolku 2": [2, 14],
  Catering: [12, 15], Toimisto: [7, 9], Lentokenttä: [22, 20],
  "Koti K1": [9, 9], "Koti K2": [5, 7], "Koti K3": [15, 11], "Koti K4": [3, 12], "Koti K5": [11, 14],
};
const ajoaika = (a, b) => {
  if (a === b) return 0;
  if (!PAIKAT[a] || !PAIKAT[b]) return 20; // tuntematon osoite -> demossa 20 min (oikeasti: karttapalvelu)
  const [x1, y1] = PAIKAT[a], [x2, y2] = PAIKAT[b];
  return Math.max(5, Math.round((Math.hypot(x1 - x2, y1 - y2) * 1.3) / 30 * 60));
};

// Päivän LISÄkustannus sopimustyypin mukaan:
//  kuukausi  = peruspalkka maksettu joka tapauksessa -> vain ylityöt maksavat
//  paiva     = päiväpalkka on aina 8 h könttä + ylityöt
//  tunti     = extra tuntipalkalla, 4 h minimi, portaat 8/10 h
const kustannus = (min, sopimus, th) => {
  const yliMin = Math.max(0, min - 8 * 60);
  const ylityo = (Math.min(yliMin, 120) / 60) * th * 1.5 + (Math.max(0, yliMin - 120) / 60) * th * 2;
  if (sopimus === "kuukausi") return ylityo;
  if (sopimus === "paiva") return 8 * th + ylityo;
  const h = Math.max(min / 60, 4);
  return Math.min(h, 8) * th + Math.max(0, Math.min(h, 10) - 8) * th * 1.5 + Math.max(0, h - 10) * th * 2;
};
const sopimusNimi = { kuukausi: "kk-sopimus", paiva: "päiväpalkka", tunti: "extra/tunti" };

// ---------- lähtödata ----------
const KUSKIT_ALKU = [
  { id: 1, nimi: "Tiina M.", puh: "040 000 0001", auto: "Farmari ABC-123", mukavuus: 3, max: 4, koti: "Koti K1", kaytossa: true, sopimus: "kuukausi" },
  { id: 2, nimi: "Eemeli K.", puh: "040 000 0002", auto: "Farmari XYZ-456", mukavuus: 3, max: 4, koti: "Koti K2", kaytossa: true, sopimus: "kuukausi" },
  { id: 3, nimi: "Sanni P.", puh: "040 000 0003", auto: "Minibussi", mukavuus: 8, max: 8, koti: "Koti K3", kaytossa: true, sopimus: "paiva" },
  { id: 4, nimi: "Emilia R.", puh: "040 000 0004", auto: "Farmari QRS-789", mukavuus: 3, max: 4, koti: "Koti K4", kaytossa: true, sopimus: "tunti" },
  { id: 5, nimi: "(vara) Kalle J.", puh: "040 000 0005", auto: "Farmari", mukavuus: 3, max: 4, koti: "Koti K5", kaytossa: false, sopimus: "tunti" },
];

const HENKILOT_ALKU = [
  { id: 1, tyyppi: "cast", nimi: "Maija Meikäläinen", roolinimi: "Komisario Aho", titteli: "", osoite: "Hotelli A", puh: "050 111 1111", mukana: true, call: "7:15", omaAuto: false, eiPaluuta: false, siirtyy: true },
  { id: 2, tyyppi: "cast", nimi: "John Example", roolinimi: "Dr. Grey", titteli: "", osoite: "Hotelli A", puh: "050 222 2222", mukana: true, call: "8:00", omaAuto: false, eiPaluuta: false, siirtyy: true },
  { id: 3, tyyppi: "cast", nimi: "Pekka Testinen", roolinimi: "Naapuri", titteli: "", osoite: "Museokuja 8", puh: "050 333 3333", mukana: true, call: "8:30", omaAuto: false, eiPaluuta: false, siirtyy: true },
  { id: 4, tyyppi: "crew", nimi: "Ritva Ohjaaja", roolinimi: "", titteli: "Ohjaaja", osoite: "Hotelli B", puh: "050 444 4444", mukana: true, call: "", omaAuto: false, eiPaluuta: false, siirtyy: true },
  { id: 5, tyyppi: "crew", nimi: "Antti Apunen", roolinimi: "", titteli: "Apulaisohjaaja", osoite: "Hotelli B", puh: "050 555 5555", mukana: true, call: "", omaAuto: true, eiPaluuta: false, siirtyy: false },
  { id: 6, tyyppi: "cast", nimi: "Liisa Latvala", roolinimi: "Sisar", titteli: "", osoite: "Rantapolku 2", puh: "050 666 6666", mukana: true, call: "14:45", omaAuto: false, eiPaluuta: false, siirtyy: false },
];

const PIKATEHTAVAT = [
  { nimi: "Lounashaku", mista: "Catering", mihin: "LOC1", hloita: 0, noutoAik: "11:15", perillaViim: "12:05", tyyppi: "tavara" },
  { nimi: "Kortit labraan", mista: "LOC2", mihin: "Toimisto", hloita: 0, noutoAik: "17:30", perillaViim: "", tyyppi: "tavara" },
  { nimi: "Lentokenttänouto", mista: "Lentokenttä", mihin: "LOC2", hloita: 1, noutoAik: "15:40", perillaViim: "16:45", tyyppi: "henkilö" },
];

const naytto = (h) => h.tyyppi === "cast" && h.roolinimi ? `${h.nimi} (${h.roolinimi})` : h.nimi;

// ---------- generointi ----------
function generoiTehtavat(paiva, henkilot) {
  const call = t(paiva.call), wrap = t(paiva.wrap), siirtyma = t(paiva.siirtyma);
  const out = []; let id = 1;
  for (const h of henkilot) {
    if (!h.mukana || h.omaAuto) continue;
    const oma = h.call ? t(h.call) : call;
    const kohde = oma >= siirtyma && paiva.loc2 ? "LOC2" : "LOC1";
    out.push({ id: id++, hloId: h.id, nimi: naytto(h), mista: h.osoite, mihin: kohde, hloita: 1, noutoAik: null, noutoViim: null, perillaViim: oma, tyyppi: "henkilö", auto: true });
    if (paiva.loc2 && h.siirtyy && kohde === "LOC1")
      out.push({ id: id++, hloId: h.id, nimi: `Siirtymä: ${naytto(h)}`, mista: "LOC1", mihin: "LOC2", hloita: 1, noutoAik: siirtyma, noutoViim: siirtyma + 20, perillaViim: siirtyma + 45, tyyppi: "siirtymä", auto: true });
    if (!h.eiPaluuta)
      out.push({ id: id++, hloId: h.id, nimi: `Paluu: ${naytto(h)}`, mista: paiva.loc2 ? "LOC2" : "LOC1", mihin: h.osoite, hloita: 1, noutoAik: wrap, noutoViim: wrap + 25, perillaViim: null, tyyppi: "paluu", auto: true });
  }
  return out;
}

// ---------- demo-optimoija (ahne, tasapainottava ja sopimustietoinen) ----------
// Periaate: kk-sopimus- ja päiväpalkkakuskien tunnit on jo maksettu -> heidän
// käyttönsä on ilmaista 8 h asti. Ylitöitä vältetään, ja tuntipalkkainen
// extra otetaan mukaan vain jos keikka ei muuten mahdu kenellekään halvemmin.
function optimoi(tehtavat, kuskit, tuntihinta) {
  const jarj = [...tehtavat].sort((a, b) => (a.perillaViim ?? a.noutoAik ?? 0) - (b.perillaViim ?? b.noutoAik ?? 0));
  const tila = kuskit.map((k) => ({ k, vapaa: 0, sijainti: k.koti, keikat: [], alku: null }));

  const sovita = (d, te) => {
    if (te.hloita > d.k.mukavuus) return null;
    let nouto = Math.max(d.vapaa + ajoaika(d.sijainti, te.mista), te.noutoAik ?? 0);
    let jatto = nouto + ajoaika(te.mista, te.mihin);
    if (te.noutoViim != null && nouto > te.noutoViim) return null;
    if (te.perillaViim != null && jatto > te.perillaViim) return null;
    if (te.perillaViim != null && jatto < te.perillaViim - 30) {
      const siirto = te.perillaViim - 30 - jatto;
      if (te.noutoViim == null || nouto + siirto <= te.noutoViim) { nouto += siirto; jatto += siirto; }
    }
    return { nouto, jatto };
  };

  const sijoittamatta = [];
  for (const te of jarj) {
    let paras = null;
    for (const d of tila) {
      const s = sovita(d, te);
      if (!s) continue;
      const alku = d.alku == null ? s.nouto : Math.min(d.alku, s.nouto);
      const span = s.jatto - alku;                                   // vuoron pituus jos keikka otetaan
      const ylityoSakko = Math.max(0, span - 8 * 60) * 3;            // 8 h päivät tavoitteena
      const extraSakko = d.keikat.length === 0 && d.k.sopimus === "tunti" ? 400 : 0;
      const tyhjaAjo = ajoaika(d.sijainti, te.mista);                // suosi lähintä vapaata
      const pisteet = tyhjaAjo * 2 + ylityoSakko + extraSakko + s.jatto * 0.02;
      if (!paras || pisteet < paras.pisteet) paras = { d, ...s, pisteet };
    }
    if (!paras) { sijoittamatta.push(te); continue; }
    paras.d.keikat.push({ ...te, nouto: paras.nouto, jatto: paras.jatto });
    paras.d.vapaa = paras.jatto;
    paras.d.sijainti = te.mihin;
    paras.d.alku = paras.d.alku == null ? paras.nouto : Math.min(paras.d.alku, paras.nouto);
  }

  const rivit = tila.filter((d) => d.keikat.length).map((d) => {
    const alku = Math.min(...d.keikat.map((x) => x.nouto));
    const loppu = Math.max(...d.keikat.map((x) => x.jatto));
    return { kuski: d.k, keikat: d.keikat, alku, loppu, kesto: loppu - alku, hinta: kustannus(loppu - alku, d.k.sopimus, tuntihinta) };
  });
  return { rivit, sijoittamatta, yhteensa: rivit.reduce((s, r) => s + r.hinta, 0) };
}

// ---------- UI-palat ----------
const pikkuLabel = { fontFamily: "'Archivo',sans-serif", fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "#77762F", marginBottom: 3 };
const vihje = { fontFamily: "'Archivo',sans-serif", fontSize: 11, color: "#77762F", fontWeight: 500, marginTop: 10, marginBottom: 0 };
const riviTyyli = { display: "flex", alignItems: "center", gap: 12, padding: "8px 0", borderBottom: `1px solid ${C.ink}`, color: C.inkSolid };
const TyyppiVari = { henkilö: C.orange, siirtymä: C.teal, paluu: C.ochre, tavara: C.olive };

const Nappi = ({ children, onClick, variant = "ink", style = {} }) => (
  <button onClick={onClick} style={{
    fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 14, padding: "10px 18px", cursor: "pointer",
    borderRadius: 999, border: `2px solid ${C.line}`,
    background: variant === "orange" ? C.orange : variant === "ghost" ? "transparent" : C.inkSolid,
    color: variant === "ghost" ? C.inkSolid : C.card,
    boxShadow: variant === "ghost" ? "none" : `3px 3px 0 ${C.line}`, ...style,
  }}>{children}</button>
);

const Ruksi = ({ checked, onChange, label }) => (
  <label style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontFamily: "'Archivo',sans-serif", fontWeight: 600, cursor: "pointer", color: C.inkSolid }}>
    <span onClick={() => onChange(!checked)} style={{ width: 18, height: 18, borderRadius: 5, border: `2px solid ${C.line}`, background: checked ? C.orange : C.card, display: "inline-flex", alignItems: "center", justifyContent: "center", color: C.card, fontSize: 12 }}>
      {checked ? "✓" : ""}
    </span>{label}
  </label>
);

const Kentta = ({ value, onChange, w = 72, ph = "" }) => (
  <input value={value} placeholder={ph} onChange={(e) => onChange(e.target.value)}
    style={{ width: w, fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600, padding: "6px 8px", border: `2px solid ${C.line}`, borderRadius: 8, background: C.card, color: C.inkSolid }} />
);

const Kortti = ({ otsikko, nro, lisa, children }) => (
  <section style={{ background: C.card, border: `2px solid ${C.line}`, borderRadius: 16, boxShadow: `5px 5px 0 ${C.line}`, padding: "18px 20px", marginBottom: 22 }}>
    <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10, flexWrap: "wrap" }}>
      <span style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: 15, width: 28, height: 28, borderRadius: 99, background: C.inkSolid, color: C.card, display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0, alignSelf: "center" }}>{nro}</span>
      <h2 style={{ fontFamily: "'Fraunces',serif", fontWeight: 700, fontSize: 20, margin: 0, color: C.inkSolid }}>{otsikko}</h2>
      {lisa && <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, fontWeight: 600, color: C.rust, marginLeft: "auto" }}>{lisa}</span>}
    </div>
    {children}
  </section>
);

// ---------- Rekisteri ----------
function Rekisteri({ henkilot, setHenkilot }) {
  const fileRef = useRef(null);
  const muuta = (id, patch) => setHenkilot(henkilot.map((h) => (h.id === id ? { ...h, ...patch } : h)));
  const poista = (id) => setHenkilot(henkilot.filter((h) => h.id !== id));
  const lisaa = (tyyppi) => setHenkilot([...henkilot, {
    id: Math.max(0, ...henkilot.map((h) => h.id)) + 1, tyyppi, nimi: "", roolinimi: "", titteli: "",
    osoite: "", puh: "", mukana: true, call: "", omaAuto: false, eiPaluuta: false, siirtyy: true,
  }]);

  const tuoExcel = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const wb = XLSX.read(new Uint8Array(ev.target.result), { type: "array" });
        const rivit = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { defval: "" });
        const etsi = (rivi, ...avaimet) => {
          for (const k of Object.keys(rivi)) if (avaimet.some((a) => k.toLowerCase().includes(a))) return String(rivi[k]);
          return "";
        };
        let id = Math.max(0, ...henkilot.map((h) => h.id));
        const uudet = rivit.map((r) => {
          const rooli = etsi(r, "rooli", "role", "character");
          return {
            id: ++id, tyyppi: rooli ? "cast" : "crew",
            nimi: etsi(r, "nimi", "name"), roolinimi: rooli, titteli: etsi(r, "titteli", "title", "osasto", "dept"),
            osoite: etsi(r, "osoite", "address"), puh: etsi(r, "puh", "phone", "tel"),
            mukana: true, call: "", omaAuto: false, eiPaluuta: false, siirtyy: true,
          };
        }).filter((h) => h.nimi);
        if (!uudet.length) { alert("Excelistä ei löytynyt rivejä. Odotetut sarakkeet: Nimi, Titteli/Rooli, Osoite, Puh."); return; }
        setHenkilot([...henkilot, ...uudet]);
      } catch (err) { alert("Tiedoston luku epäonnistui: " + err.message); }
    };
    reader.readAsArrayBuffer(file);
    e.target.value = "";
  };

  const ryhma = (tyyppi, otsikko, nro) => (
    <Kortti otsikko={otsikko} nro={nro}>
      {henkilot.filter((h) => h.tyyppi === tyyppi).map((h) => (
        <div key={h.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
          <Kentta value={h.nimi} onChange={(v) => muuta(h.id, { nimi: v })} w={150} ph="Nimi" />
          {tyyppi === "cast"
            ? <Kentta value={h.roolinimi} onChange={(v) => muuta(h.id, { roolinimi: v })} w={120} ph="Roolinimi" />
            : <Kentta value={h.titteli} onChange={(v) => muuta(h.id, { titteli: v })} w={120} ph="Titteli" />}
          <Kentta value={h.osoite} onChange={(v) => muuta(h.id, { osoite: v })} w={120} ph="Osoite" />
          <Kentta value={h.puh} onChange={(v) => muuta(h.id, { puh: v })} w={110} ph="Puhelin" />
          <span style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center" }}>
            <Ruksi checked={h.mukana} onChange={(v) => muuta(h.id, { mukana: v })} label="mukana tänään" />
            <button onClick={() => poista(h.id)} style={{ border: "none", background: "none", cursor: "pointer", color: C.rust, fontWeight: 900, fontSize: 16 }}>×</button>
          </span>
        </div>
      ))}
      <div style={{ marginTop: 12 }}>
        <Nappi variant="ghost" onClick={() => lisaa(tyyppi)}>+ Lisää {tyyppi === "cast" ? "näyttelijä" : "työryhmäläinen"}</Nappi>
      </div>
    </Kortti>
  );

  return (
    <div>
      <div style={{ display: "flex", gap: 10, marginBottom: 18, alignItems: "center", flexWrap: "wrap" }}>
        <Nappi onClick={() => fileRef.current?.click()}>⇪ Tuo Excelistä</Nappi>
        <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={tuoExcel} style={{ display: "none" }} />
        <span style={{ ...vihje, marginTop: 0 }}>Sarakkeet: Nimi, Titteli tai Rooli, Osoite, Puh — järjestyksellä ei väliä.</span>
      </div>
      {ryhma("cast", "Näyttelijät", "A")}
      {ryhma("crew", "Työryhmä", "B")}
      <p style={vihje}>Demossa optimoija tuntee vain esimerkkiosoitteet — tuntemattomille se käyttää 20 min ajoaikaa. Oikeassa versiossa osoitteet geokoodataan karttapalvelusta.</p>
    </div>
  );
}

// ---------- Vaihe 1: Pohjatiedot ----------
function Pohjatiedot({ paiva, setPaiva, kuskit, setKuskit, henkilot, setHenkilot }) {
  const muutaH = (id, patch) => setHenkilot(henkilot.map((h) => (h.id === id ? { ...h, ...patch } : h)));
  const muutaK = (id, patch) => setKuskit(kuskit.map((k) => (k.id === id ? { ...k, ...patch } : k)));
  return (
    <div>
      <Kortti otsikko="Päivän ajat" nro="A">
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
          {[["Call time", "call"], ["Lounas", "lounas"], ["Siirtymä LOC1→LOC2", "siirtyma"], ["Wrap", "wrap"]].map(([lab, key]) => (
            <div key={key}><div style={pikkuLabel}>{lab}</div><Kentta value={paiva[key]} onChange={(v) => setPaiva({ ...paiva, [key]: v })} /></div>
          ))}
          <div><div style={pikkuLabel}>Kuskin €/h</div><Kentta value={paiva.tuntihinta} onChange={(v) => setPaiva({ ...paiva, tuntihinta: v })} w={56} /></div>
          <div style={{ alignSelf: "flex-end" }}>
            <Ruksi checked={paiva.loc2} onChange={(v) => setPaiva({ ...paiva, loc2: v })} label="Päivässä on toinen lokaatio" />
          </div>
        </div>
        <p style={vihje}>Lisäkustannus sopimuksen mukaan: kk-sopimus = vain ylityöt maksavat · päiväpalkka = 8 h könttä + ylityöt · extra = tuntipalkka, 4 h minimi. Ylityöt 8–10 h ×1,5, yli 10 h ×2. Työaika = eka nouto → viimeinen jättö.</p>
      </Kortti>

      <Kortti otsikko="Kuskit ja autot" nro="B">
        {kuskit.map((k) => (
          <div key={k.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
            <Kentta value={k.nimi} onChange={(v) => muutaK(k.id, { nimi: v })} w={120} ph="Kuskin nimi" />
            <Kentta value={k.puh} onChange={(v) => muutaK(k.id, { puh: v })} w={110} ph="Puhelin" />
            <Kentta value={k.auto} onChange={(v) => muutaK(k.id, { auto: v })} w={140} ph="Auto" />
            <select value={k.sopimus} onChange={(e) => muutaK(k.id, { sopimus: e.target.value })}
              style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 12, padding: "6px 8px", border: `2px solid ${C.line}`, borderRadius: 8, background: C.card, color: C.inkSolid, cursor: "pointer" }}>
              <option value="kuukausi">kk-sopimus</option>
              <option value="paiva">päiväpalkka</option>
              <option value="tunti">extra / tuntipalkka</option>
            </select>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={pikkuLabel}>mukavuus</span>
              <Kentta value={String(k.mukavuus)} onChange={(v) => muutaK(k.id, { mukavuus: Number(v) || 0 })} w={36} />
              <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive }}>/ {k.max} paikkaa</span>
            </span>
            <span style={{ marginLeft: "auto" }}>
              <Ruksi checked={k.kaytossa} onChange={(v) => muutaK(k.id, { kaytossa: v })} label="tarjolla" />
            </span>
          </div>
        ))}
        <p style={vihje}>Optimoija käyttää mukavuuspaikkoja (farkku = 3, ettei kolme aikuista änge takapenkille). Max paikat = hätävara, jonka ylitys vaatii käsin hyväksynnän — tulossa oikeaan versioon.</p>
      </Kortti>

      <Kortti otsikko="Tämän päivän kuskattavat" nro="C">
        {henkilot.filter((h) => h.mukana).map((h) => (
          <div key={h.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, minWidth: 170, fontSize: 13 }}>
              {naytto(h)}
              {h.titteli && <span style={{ fontWeight: 500, color: C.olive }}> · {h.titteli}</span>}
            </span>
            <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12 }}>{h.osoite}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={pikkuLabel}>call</span>
              <Kentta value={h.call} onChange={(v) => muutaH(h.id, { call: v })} w={60} ph="yleinen" />
            </span>
            <span style={{ display: "flex", gap: 10, marginLeft: "auto", flexWrap: "wrap" }}>
              <Ruksi checked={h.omaAuto} onChange={(v) => muutaH(h.id, { omaAuto: v })} label="oma auto" />
              <Ruksi checked={h.eiPaluuta} onChange={(v) => muutaH(h.id, { eiPaluuta: v })} label="ei paluuta" />
              <Ruksi checked={h.siirtyy} onChange={(v) => muutaH(h.id, { siirtyy: v })} label="siirtymässä" />
            </span>
          </div>
        ))}
        <p style={vihje}>Puuttuuko joku? Lisää hänet Rekisteri-välilehdellä ja ruksi "mukana tänään".</p>
      </Kortti>
    </div>
  );
}

// ---------- Vaihe 2: Tehtävät ----------
function Tehtavat({ tehtavat, setTehtavat }) {
  const [uusi, setUusi] = useState({ nimi: "", mista: "LOC1", mihin: "LOC2", noutoAik: "", perillaViim: "", hloita: 1 });
  const poista = (id) => setTehtavat(tehtavat.filter((x) => x.id !== id));
  const lisaaPika = (p) => setTehtavat([...tehtavat, {
    id: Math.max(0, ...tehtavat.map((x) => x.id)) + 1, hloId: null,
    nimi: p.nimi, mista: p.mista, mihin: p.mihin, hloita: p.hloita,
    noutoAik: p.noutoAik ? t(p.noutoAik) : null, noutoViim: null,
    perillaViim: p.perillaViim ? t(p.perillaViim) : null, tyyppi: p.tyyppi, auto: false,
  }]);
  return (
    <div>
      <Kortti otsikko="Generoitu tehtävälista" nro="A">
        <p style={{ ...vihje, marginTop: 0 }}>Softan luonnos pohjatiedoista — poista turhat, lisää erikoiskeikat. Tämä lista on optimoijan totuus.</p>
        {tehtavat.map((te) => (
          <div key={te.id} style={riviTyyli}>
            <span style={{ width: 10, height: 10, borderRadius: 99, background: TyyppiVari[te.tyyppi], border: `2px solid ${C.line}`, flexShrink: 0 }} />
            <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, minWidth: 160, fontSize: 13 }}>{te.nimi}</span>
            <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12 }}>{te.mista} → {te.mihin}</span>
            <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: C.rust, fontWeight: 600 }}>
              {te.perillaViim != null ? `perillä ${hhmm(te.perillaViim)}` : te.noutoAik != null ? `nouto ${hhmm(te.noutoAik)}${te.noutoViim ? "–" + hhmm(te.noutoViim) : "→"}` : ""}
            </span>
            {!te.auto && <span style={{ fontSize: 10, fontFamily: "'Archivo',sans-serif", fontWeight: 700, background: C.ochre, border: `2px solid ${C.line}`, borderRadius: 99, padding: "1px 8px" }}>käsin</span>}
            <button onClick={() => poista(te.id)} style={{ marginLeft: "auto", border: "none", background: "none", cursor: "pointer", color: C.rust, fontWeight: 900, fontSize: 16 }}>×</button>
          </div>
        ))}
      </Kortti>

      <Kortti otsikko="Lisää tehtävä" nro="B">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 14 }}>
          {PIKATEHTAVAT.map((p) => (
            <button key={p.nimi} onClick={() => lisaaPika(p)} style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 12, padding: "6px 12px", borderRadius: 99, border: `2px dashed ${C.line}`, background: C.card, cursor: "pointer", color: C.inkSolid }}>
              + {p.nimi}
            </button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div><div style={pikkuLabel}>Nimi</div><Kentta value={uusi.nimi} onChange={(v) => setUusi({ ...uusi, nimi: v })} w={160} /></div>
          <div><div style={pikkuLabel}>Mistä</div><Kentta value={uusi.mista} onChange={(v) => setUusi({ ...uusi, mista: v })} w={100} /></div>
          <div><div style={pikkuLabel}>Mihin</div><Kentta value={uusi.mihin} onChange={(v) => setUusi({ ...uusi, mihin: v })} w={100} /></div>
          <div><div style={pikkuLabel}>Nouto aik.</div><Kentta value={uusi.noutoAik} onChange={(v) => setUusi({ ...uusi, noutoAik: v })} w={60} /></div>
          <div><div style={pikkuLabel}>Perillä viim.</div><Kentta value={uusi.perillaViim} onChange={(v) => setUusi({ ...uusi, perillaViim: v })} w={60} /></div>
          <Nappi variant="ghost" onClick={() => { if (uusi.nimi) { lisaaPika({ ...uusi, tyyppi: uusi.hloita > 0 ? "henkilö" : "tavara" }); setUusi({ ...uusi, nimi: "" }); } }}>+ Lisää</Nappi>
        </div>
      </Kortti>
    </div>
  );
}

// ---------- Vaihe 3: Ajolista (suunnittelu + tulostus) ----------
function Ajolista({ tulos, laskee, optimoiNyt, skenaariot, paiva, henkilot }) {
  const [nakyma, setNakyma] = useState("suunnittelu");
  const MIN = 6 * 60, MAX = 21 * 60, W = MAX - MIN;
  const puh = (hloId) => henkilot.find((h) => h.id === hloId)?.puh || "";

  return (
    <div>
      <div className="ei-printtiin" style={{ display: "flex", alignItems: "center", gap: 12, margin: "18px 0", flexWrap: "wrap" }}>
        <Nappi variant="orange" onClick={optimoiNyt}>{laskee ? "Lasketaan…" : tulos ? "↻ Optimoi uudelleen" : "★ Optimoi ajolista"}</Nappi>
        {tulos && (
          <>
            <div style={{ display: "flex", border: `2px solid ${C.line}`, borderRadius: 999, overflow: "hidden" }}>
              {[["suunnittelu", "Suunnittelu €"], ["tulostus", "Tulostusversio"]].map(([k, lab]) => (
                <button key={k} onClick={() => setNakyma(k)} style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 12, padding: "8px 14px", border: "none", cursor: "pointer", background: nakyma === k ? C.inkSolid : C.card, color: nakyma === k ? C.card : C.inkSolid }}>{lab}</button>
              ))}
            </div>
            {nakyma === "tulostus" && <Nappi variant="ghost" onClick={() => window.print()}>🖨 Tulosta</Nappi>}
          </>
        )}
      </div>

      {tulos && tulos.sijoittamatta.length > 0 && (
        <div className="ei-printtiin" style={{ border: `2px solid ${C.rust}`, background: "#F7DFD2", borderRadius: 12, padding: "10px 14px", marginBottom: 16, fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 13, color: C.rust }}>
          ⚠ Sijoittamatta jäi: {tulos.sijoittamatta.map((x) => x.nimi).join(", ")} — lisää kuski tai väljennä aikaikkunoita.
        </div>
      )}

      {/* ---------- SUUNNITTELUNÄKYMÄ (kustannukset näkyvissä) ---------- */}
      {tulos && nakyma === "suunnittelu" && (
        <>
          <div style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: 30, marginBottom: 16 }}>
            +{Math.round(tulos.yhteensa)} €
            <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 12, marginLeft: 10, color: C.olive }}>päivän lisäkustannus (kk-sopparien peruspalkka jo maksettu) · {tulos.rivit.length} kuskia</span>
          </div>
          {tulos.rivit.map((r, i) => (
            <Kortti key={i} otsikko={`${r.kuski.nimi} · ${r.kuski.auto}`} nro={String(i + 1)}
              lisa={`${hhmm(r.alku)}–${hhmm(r.loppu)} · ${Math.floor(r.kesto / 60)}h ${String(r.kesto % 60).padStart(2, "0")}min · ${sopimusNimi[r.kuski.sopimus]} · +${Math.round(r.hinta)} €${r.kesto > 8 * 60 ? " · YLITYÖTÄ" : ""}`}>
              <div style={{ position: "relative", height: 34, background: C.paper, border: `2px solid ${C.line}`, borderRadius: 8, marginBottom: 12, overflow: "hidden" }}>
                {[8, 10, 12, 14, 16, 18, 20].map((h) => (
                  <div key={h} style={{ position: "absolute", left: `${((h * 60 - MIN) / W) * 100}%`, top: 0, bottom: 0, borderLeft: `1px dashed ${C.ink}`, fontSize: 9, fontFamily: "'IBM Plex Mono',monospace", paddingLeft: 2 }}>{h}</div>
                ))}
                {r.keikat.map((k, j) => (
                  <div key={j} title={`${k.nimi} ${hhmm(k.nouto)}–${hhmm(k.jatto)}`}
                    style={{ position: "absolute", top: 6, height: 18, borderRadius: 6, border: `2px solid ${C.line}`, background: TyyppiVari[k.tyyppi], left: `${((k.nouto - MIN) / W) * 100}%`, width: `${Math.max(1.2, ((k.jatto - k.nouto) / W) * 100)}%` }} />
                ))}
              </div>
              {r.keikat.map((k, j) => (
                <div key={j} style={{ ...riviTyyli, padding: "5px 0" }}>
                  <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, fontSize: 13, width: 96 }}>{hhmm(k.nouto)}–{hhmm(k.jatto)}</span>
                  <span style={{ width: 8, height: 8, borderRadius: 99, background: TyyppiVari[k.tyyppi], flexShrink: 0 }} />
                  <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 13 }}>{k.nimi}</span>
                  <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive, marginLeft: "auto" }}>{k.mista} → {k.mihin}</span>
                </div>
              ))}
            </Kortti>
          ))}
          {skenaariot && (
            <Kortti otsikko="Montako kuskia kannattaa ottaa?" nro="€">
              {skenaariot.map((s) => (
                <div key={s.n} style={{ ...riviTyyli, fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600 }}>
                  <span>{s.n} tarjolla → {s.kaytossa} käytössä</span>
                  <span style={{ marginLeft: "auto", fontWeight: 700, color: s.paras ? C.orange : C.inkSolid }}>
                    {s.ok ? `${Math.round(s.hinta)} €` : "ei ratkaisua"}{s.paras ? "  ★ halvin" : ""}
                  </span>
                </div>
              ))}
              <p style={vihje}>Demo-optimointi on yksinkertaistettu (ei kimppakyytejä). Oikea versio käyttää OR-Toolsia backendissä.</p>
            </Kortti>
          )}
        </>
      )}

      {/* ---------- TULOSTUSVERSIO (ei kustannuksia) ---------- */}
      {tulos && nakyma === "tulostus" && (
        <div style={{ background: "#fff", border: `2px solid ${C.line}`, borderRadius: 4, padding: "28px 32px", fontFamily: "'Archivo',sans-serif", color: "#111" }}>
          <div style={{ borderBottom: "3px solid #111", paddingBottom: 10, marginBottom: 16 }}>
            <div style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: 26 }}>AJOLISTA — TO 9.7.</div>
            <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, marginTop: 4 }}>
              CALL {paiva.call} · LOUNAS {paiva.lounas} · SIIRTYMÄ LOC1→LOC2 {paiva.siirtyma} · WRAP {paiva.wrap}
            </div>
          </div>
          {tulos.rivit.map((r, i) => (
            <div key={i} style={{ marginBottom: 22 }}>
              <div style={{ fontWeight: 700, fontSize: 15, borderBottom: "2px solid #111", paddingBottom: 4, marginBottom: 6, display: "flex", justifyContent: "space-between", flexWrap: "wrap" }}>
                <span>{r.kuski.nimi} · {r.kuski.auto}</span>
                <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600 }}>{r.kuski.puh}</span>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ textAlign: "left", fontFamily: "'IBM Plex Mono',monospace", fontSize: 11 }}>
                    <th style={{ padding: "3px 6px 3px 0" }}>NOUTO</th><th>KUKA / MIKÄ</th><th>MISTÄ → MIHIN</th><th>PUH</th>
                  </tr>
                </thead>
                <tbody>
                  {r.keikat.map((k, j) => (
                    <tr key={j} style={{ borderTop: "1px solid #999" }}>
                      <td style={{ fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, padding: "4px 6px 4px 0", whiteSpace: "nowrap" }}>{hhmm(k.nouto)}</td>
                      <td style={{ padding: "4px 6px 4px 0" }}>{k.nimi}</td>
                      <td style={{ padding: "4px 6px 4px 0" }}>{k.mista} → {k.mihin}</td>
                      <td style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, whiteSpace: "nowrap" }}>{puh(k.hloId)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: "#555" }}>Ei kustannustietoja — jaettava versio kuskeille ja työryhmälle.</div>
        </div>
      )}

      {!tulos && !laskee && (
        <div style={{ textAlign: "center", padding: "60px 20px", fontFamily: "'Archivo',sans-serif", color: C.olive, fontWeight: 600 }}>
          Paina ★ Optimoi — ajolista rakentuu tehtävälistasta.
        </div>
      )}
    </div>
  );
}

// ---------- App ----------
export default function App() {
  const [tab, setTab] = useState("rekisteri");
  const [paiva, setPaiva] = useState({ call: "8:45", lounas: "12:30", siirtyma: "14:00", wrap: "17:30", loc2: true, tuntihinta: "22" });
  const [kuskit, setKuskit] = useState(KUSKIT_ALKU);
  const [henkilot, setHenkilot] = useState(HENKILOT_ALKU);
  const [tehtavat, setTehtavat] = useState(null);
  const [tulos, setTulos] = useState(null);
  const [skenaariot, setSkenaariot] = useState(null);
  const [laskee, setLaskee] = useState(false);

  const siirry = (uusiTab) => {
    if ((uusiTab === "tehtavat" || uusiTab === "ajolista") && tehtavat === null)
      setTehtavat(generoiTehtavat(paiva, henkilot));
    setTab(uusiTab);
  };

  const optimoiNyt = () => {
    setLaskee(true); setTulos(null);
    setTimeout(() => {
      const th = Number(paiva.tuntihinta) || 22;
      const aktiiviset = kuskit.filter((k) => k.kaytossa);
      const paatulos = optimoi(tehtavat, aktiiviset, th);
      const sken = [];
      for (let n = Math.max(2, aktiiviset.length - 2); n <= aktiiviset.length; n++) {
        const r = optimoi(tehtavat, aktiiviset.slice(0, n), th);
        sken.push({ n, kaytossa: r.rivit.length, hinta: r.yhteensa, ok: r.sijoittamatta.length === 0 });
      }
      const kelvot = sken.filter((s) => s.ok);
      const halvin = kelvot.length ? Math.min(...kelvot.map((s) => s.hinta)) : null;
      sken.forEach((s) => (s.paras = s.ok && s.hinta === halvin));
      setTulos(paatulos); setSkenaariot(sken); setLaskee(false);
    }, 700);
  };

  const TABS = [["rekisteri", "☰ Rekisteri"], ["pohjatiedot", "1 · Pohjatiedot"], ["tehtavat", "2 · Tehtävät"], ["ajolista", "3 · Ajolista"]];

  return (
    <div style={{ minHeight: "100vh", background: C.paper, color: C.inkSolid, paddingBottom: 80 }}>
      <style>{FONTS}</style>

      <header className="ei-printtiin" style={{ borderBottom: `3px solid ${C.line}`, background: C.paper }}>
        <div style={{ height: 10, display: "flex" }}>
          {[C.rust, C.orange, C.ochre, C.olive, C.teal].map((c) => <div key={c} style={{ flex: 1, background: c }} />)}
        </div>
        <div style={{ maxWidth: 900, margin: "0 auto", padding: "22px 20px 14px", display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
          <h1 style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: "clamp(34px, 7vw, 52px)", margin: 0, letterSpacing: "-0.02em", lineHeight: 0.95 }}>
            AJO<span style={{ color: C.orange }}>LISTA</span>
          </h1>
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, fontWeight: 600, color: C.olive }}>KUVAUSPÄIVÄ 22/49 · TO 9.7. · demo v2</span>
        </div>
      </header>

      <main style={{ maxWidth: 900, margin: "0 auto", padding: "0 20px" }}>
        <nav className="ei-printtiin" style={{ display: "flex", gap: 8, margin: "20px 0 26px", flexWrap: "wrap" }}>
          {TABS.map(([k, nimi]) => (
            <button key={k} onClick={() => siirry(k)} style={{
              fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 13, cursor: "pointer",
              padding: "8px 16px", borderRadius: 999, border: `2px solid ${C.line}`,
              background: tab === k ? C.inkSolid : C.card, color: tab === k ? C.card : C.inkSolid,
              boxShadow: tab === k ? `3px 3px 0 ${C.orange}` : "none",
            }}>{nimi}</button>
          ))}
        </nav>

        {tab === "rekisteri" && <Rekisteri {...{ henkilot, setHenkilot }} />}
        {tab === "pohjatiedot" && <Pohjatiedot {...{ paiva, setPaiva, kuskit, setKuskit, henkilot, setHenkilot }} />}
        {tab === "tehtavat" && tehtavat && <Tehtavat {...{ tehtavat, setTehtavat }} />}
        {tab === "ajolista" && tehtavat && <Ajolista {...{ tulos, laskee, optimoiNyt, skenaariot, paiva, henkilot }} />}

        <div className="ei-printtiin" style={{ display: "flex", gap: 10, marginTop: 8 }}>
          {tab === "rekisteri" && <Nappi variant="orange" onClick={() => siirry("pohjatiedot")} style={{ marginLeft: "auto" }}>Pohjatietoihin →</Nappi>}
          {tab === "pohjatiedot" && <Nappi variant="orange" onClick={() => { setTehtavat(generoiTehtavat(paiva, henkilot)); setTab("tehtavat"); }} style={{ marginLeft: "auto" }}>Generoi tehtävät →</Nappi>}
          {tab === "tehtavat" && <Nappi variant="orange" onClick={() => siirry("ajolista")} style={{ marginLeft: "auto" }}>Optimointiin →</Nappi>}
        </div>
      </main>
    </div>
  );
}

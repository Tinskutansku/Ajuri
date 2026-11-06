import { useEffect, useState } from "react";
import { C, Kortti, Nappi, Kentta, Ruksi, Badge, riviTyyli, pikkuLabel, vihje } from "./ui.jsx";
import * as api from "./api.js";

/* Tehtävät — päivän kuljetustehtävät: generointi Pohjatiedoista
   (POST /paivat/{id}/generoi-tehtavat) sekä käsin lisätyt erikoiskeikat
   (lounashaku, kortit, lentokenttänouto…). Generoidut ja käsin lisätyt
   erotetaan badgella, koska uudelleengenerointi korvaa vain generoidut. */

// Sama aikamuunnos kuin Pohjatiedoissa: backend "HH:MM:SS" <-> input "HH:MM",
// tyhjä kenttä tallentuu null:ina.
const aikaIn = (v) => (v ? String(v).slice(0, 5) : "");
const aikaOut = (v) => {
  const s = String(v ?? "").trim();
  return s === "" ? null : s;
};

const TYYPIT = [
  ["henkilo", "nouto"],
  ["siirtyma", "siirtymä"],
  ["paluu", "paluu"],
  ["tavara", "tavara"],
];
const tyyppiNimi = Object.fromEntries(TYYPIT);

const AIKAKENTAT = [
  ["nouto_aikaisintaan", "nouto aikaisintaan"],
  ["nouto_viimeistaan", "nouto viimeistään"],
  ["perilla_aikaisintaan", "perillä aikaisintaan"],
  ["perilla_viimeistaan", "perillä viimeistään"],
];

const valintaTyyli = {
  fontFamily: "'Archivo',sans-serif",
  fontWeight: 600,
  fontSize: 12,
  padding: "6px 8px",
  border: `2px solid ${C.line}`,
  borderRadius: 8,
  background: C.card,
  color: C.inkSolid,
  cursor: "pointer",
};

const henkiloNimi = (h) =>
  h.tyyppi === "cast" && h.roolinimi ? `${h.nimi} (${h.roolinimi})` : h.nimi;

const onKoordinaatit = (lat, lon) => lat != null && lon != null;

// Lajitteluavain: aikaisin tunnettu kellonaika, aikattomat loppuun.
const aikaAvain = (r) => {
  const ajat = AIKAKENTAT.map(([k]) => r[k]).filter(Boolean).map((s) => String(s).slice(0, 5));
  return ajat.length ? ajat.sort()[0] : "99:99";
};

const tyhjaLomake = (paivaId) => ({
  id: null,
  paiva_id: Number(paivaId),
  tyyppi: "tavara",
  nimi: "",
  henkilo_id: "",
  henkiloita: 0,
  mista_osoite: "",
  mista_lat: null,
  mista_lon: null,
  mihin_osoite: "",
  mihin_lat: null,
  mihin_lon: null,
  nouto_aikaisintaan: "",
  nouto_viimeistaan: "",
  perilla_aikaisintaan: "",
  perilla_viimeistaan: "",
  generoitu: false,
  aktiivinen: true,
  lukittu_kuski_id: "",
  yksin: false,
  huomiot: "",
});

const lomakkeeksi = (r) => ({
  ...r,
  henkilo_id: r.henkilo_id ?? "",
  lukittu_kuski_id: r.lukittu_kuski_id ?? "",
  huomiot: r.huomiot ?? "",
  ...Object.fromEntries(AIKAKENTAT.map(([k]) => [k, aikaIn(r[k])])),
});

const payload = (l) => ({
  paiva_id: l.paiva_id,
  tyyppi: l.tyyppi,
  nimi: l.nimi.trim(),
  henkilo_id: l.henkilo_id === "" ? null : Number(l.henkilo_id),
  henkiloita: Math.max(0, Number(l.henkiloita) || 0),
  mista_osoite: l.mista_osoite.trim(),
  mista_lat: l.mista_lat,
  mista_lon: l.mista_lon,
  mihin_osoite: l.mihin_osoite.trim(),
  mihin_lat: l.mihin_lat,
  mihin_lon: l.mihin_lon,
  ...Object.fromEntries(AIKAKENTAT.map(([k]) => [k, aikaOut(l[k])])),
  // Muokkaus ei muuta generoitu-lippua: generoitu rivi pysyy generoituna,
  // ja seuraava generointi korvaa sen (ks. vihje lomakkeessa).
  generoitu: l.generoitu,
  aktiivinen: l.aktiivinen,
  lukittu_kuski_id: l.lukittu_kuski_id === "" ? null : Number(l.lukittu_kuski_id),
  yksin: l.yksin,
  huomiot: l.huomiot.trim() || null,
});

/* Paikkavalitsin: tuotannon lokaatiot ja henkilöiden kotiosoitteet tuovat
   koordinaatit mukanaan. Vapaa osoite tallentuu ilman koordinaatteja, koska
   POST /tehtavat ei geokoodaa — optimointi vaatii koordinaatit. */
function Paikka({ otsikko, osoite, lat, lon, paikat, onChange }) {
  const valittu =
    paikat.find((p) => p.osoite === osoite && p.lat === lat && p.lon === lon)?.avain ?? "";
  return (
    <div style={{ flex: "1 1 260px" }}>
      <div style={pikkuLabel}>{otsikko}</div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <select
          value={valittu}
          onChange={(e) => {
            const p = paikat.find((x) => x.avain === e.target.value);
            if (p) onChange({ osoite: p.osoite, lat: p.lat, lon: p.lon });
            else onChange({ osoite: "", lat: null, lon: null });
          }}
          style={{ ...valintaTyyli, maxWidth: 220 }}
        >
          <option value="">— muu osoite —</option>
          {paikat.map((p) => (
            <option key={p.avain} value={p.avain}>
              {p.nimi}
            </option>
          ))}
        </select>
        <Kentta
          value={osoite}
          // Käsin muutettu osoite ei enää vastaa vanhoja koordinaatteja.
          onChange={(v) => onChange({ osoite: v, lat: null, lon: null })}
          w={220}
          ph="osoite"
        />
      </div>
      <div style={{ ...vihje, marginTop: 4, color: onKoordinaatit(lat, lon) ? C.teal : C.rust }}>
        {onKoordinaatit(lat, lon)
          ? "📍 koordinaatit ok"
          : "⚠ ei koordinaatteja — valitse paikka listalta, tai lisää se lokaatioksi Pohjatiedoissa"}
      </div>
    </div>
  );
}

export default function Tehtavat() {
  const [tuotannot, setTuotannot] = useState([]);
  const [tuotantoId, setTuotantoId] = useState("");
  const [paivat, setPaivat] = useState([]);
  const [paivaId, setPaivaId] = useState("");

  const [lokaatiot, setLokaatiot] = useState([]);
  const [henkilot, setHenkilot] = useState([]);
  const [kuskit, setKuskit] = useState([]);

  const [tehtavat, setTehtavat] = useState([]);
  const [lomake, setLomake] = useState(null); // null = kiinni
  const [generoi, setGeneroi] = useState(false);
  const [varoitus, setVaroitus] = useState(null);
  const [ilmoitus, setIlmoitus] = useState(null);
  const [virhe, setVirhe] = useState(null);

  useEffect(() => {
    api
      .haeTuotannot()
      .then((d) => {
        setTuotannot(d);
        if (d.length) setTuotantoId(String(d[0].id));
      })
      .catch((e) => setVirhe(e.message));
  }, []);

  useEffect(() => {
    if (!tuotantoId) return;
    setPaivaId("");
    Promise.all([
      api.haeKuvauspaivatTuotannolle(tuotantoId),
      api.haeLokaatiot(tuotantoId),
      api.haeHenkilot(tuotantoId),
      api.haeKuskit(tuotantoId),
    ])
      .then(([ps, ls, hs, ks]) => {
        setPaivat(ps);
        setLokaatiot(ls);
        setHenkilot(hs);
        setKuskit(ks);
        if (ps.length) setPaivaId(String(ps[ps.length - 1].id));
      })
      .catch((e) => setVirhe(e.message));
  }, [tuotantoId]);

  useEffect(() => {
    setLomake(null);
    setVaroitus(null);
    setIlmoitus(null);
    if (!paivaId) {
      setTehtavat([]);
      return;
    }
    api
      .haeTehtavat(paivaId)
      .then(setTehtavat)
      .catch((e) => setVirhe(e.message));
  }, [paivaId]);

  const paiva = paivat.find((p) => String(p.id) === String(paivaId));
  const generoidut = tehtavat.filter((r) => r.generoitu);
  const kasin = tehtavat.filter((r) => !r.generoitu);
  const jarjestetyt = [...tehtavat].sort((a, b) => {
    const ka = aikaAvain(a);
    const kb = aikaAvain(b);
    return ka === kb ? a.id - b.id : ka < kb ? -1 : 1;
  });
  const ilmanKoordinaatteja = tehtavat.filter(
    (r) => !onKoordinaatit(r.mista_lat, r.mista_lon) || !onKoordinaatit(r.mihin_lat, r.mihin_lon)
  ).length;

  const paikat = [
    ...lokaatiot
      .filter((l) => l.osoite)
      .map((l) => ({ avain: `l${l.id}`, nimi: `◆ ${l.nimi}`, osoite: l.osoite, lat: l.lat, lon: l.lon })),
    ...henkilot
      .filter((h) => h.osoite)
      .map((h) => ({ avain: `h${h.id}`, nimi: `☰ ${henkiloNimi(h)} (koti)`, osoite: h.osoite, lat: h.lat, lon: h.lon })),
  ];

  // --- Generointi ---

  const generoiTehtavat = async () => {
    if (
      generoidut.length &&
      !window.confirm(
        `Uudelleengenerointi korvaa ${generoidut.length} generoitua tehtävää ` +
          `(myös niihin tehdyt muokkaukset). Käsin lisättyjä ei kosketa. Jatketaanko?`
      )
    )
      return;
    setGeneroi(true);
    setVirhe(null);
    setIlmoitus(null);
    try {
      const vastaus = await api.generoiTehtavat(paivaId);
      setVaroitus(vastaus.varoitus);
      setTehtavat(await api.haeTehtavat(paivaId));
      setIlmoitus(`Generoitu ${vastaus.tehtavat.length} tehtävää.`);
      setLomake(null);
    } catch (e) {
      setVirhe(e.message);
    } finally {
      setGeneroi(false);
    }
  };

  // --- Käsin lisäys, muokkaus, poisto ---

  const lokaatioNimella = (re) => lokaatiot.find((l) => re.test(l.nimi) && l.osoite);
  const kuvauspaikka = () => lokaatiot.find((l) => l.osoite);

  const avaaPohja = (pohja) => {
    const l = tyhjaLomake(paivaId);
    const kp = kuvauspaikka();
    const kohde = kp ? { mihin_osoite: kp.osoite, mihin_lat: kp.lat, mihin_lon: kp.lon } : {};
    if (pohja === "lounas") {
      setLomake({ ...l, ...kohde, nimi: "Lounashaku", perilla_viimeistaan: aikaIn(paiva?.lounas) });
    } else if (pohja === "kortit") {
      setLomake({ ...l, ...kohde, nimi: "Kortit" });
    } else if (pohja === "lento") {
      const lento = lokaatioNimella(/lento|airport/i);
      setLomake({
        ...l,
        ...kohde,
        tyyppi: "henkilo",
        henkiloita: 1,
        nimi: "Lentokenttänouto",
        ...(lento
          ? { mista_osoite: lento.osoite, mista_lat: lento.lat, mista_lon: lento.lon }
          : { mista_osoite: "Helsinki-Vantaan lentoasema" }),
      });
    } else {
      setLomake(l);
    }
    setVirhe(null);
  };

  const muuta = (patch) => setLomake((l) => ({ ...l, ...patch }));

  const tallenna = async () => {
    if (!lomake.nimi.trim()) return setVirhe("Tehtävällä pitää olla nimi.");
    if (!lomake.mista_osoite.trim() || !lomake.mihin_osoite.trim())
      return setVirhe("Tehtävällä pitää olla sekä mistä- että mihin-osoite.");
    try {
      const data = payload(lomake);
      const r = lomake.id ? await api.paivitaTehtava(lomake.id, data) : await api.luoTehtava(data);
      setTehtavat((rs) => (lomake.id ? rs.map((x) => (x.id === r.id ? r : x)) : [...rs, r]));
      setLomake(null);
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const poista = async (r) => {
    if (!window.confirm(`Poistetaanko tehtävä "${r.nimi}"?`)) return;
    try {
      await api.poistaTehtava(r.id);
      setTehtavat((rs) => rs.filter((x) => x.id !== r.id));
      if (lomake?.id === r.id) setLomake(null);
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  // --- Renderöinti ---

  const kuskiNimi = (id) => kuskit.find((k) => k.id === id)?.nimi ?? `kuski #${id}`;

  const aikaTeksti = (r) => {
    const osat = [];
    const n1 = aikaIn(r.nouto_aikaisintaan);
    const n2 = aikaIn(r.nouto_viimeistaan);
    const p1 = aikaIn(r.perilla_aikaisintaan);
    const p2 = aikaIn(r.perilla_viimeistaan);
    if (n1 || n2) osat.push(`nouto ${n1 || "…"}–${n2 || "…"}`);
    if (p1 || p2) osat.push(`perillä ${p1 ? `${p1}–` : ""}${p2 ? `viim. ${p2}` : "…"}`);
    return osat.join(" · ") || "ei aikaikkunaa";
  };

  const tehtavaRivi = (r) => {
    const koordOk = onKoordinaatit(r.mista_lat, r.mista_lon) && onKoordinaatit(r.mihin_lat, r.mihin_lon);
    const muokataan = lomake?.id === r.id;
    return (
      <div key={r.id} style={{ ...riviTyyli, flexWrap: "wrap", alignItems: "flex-start", background: muokataan ? "#F7E7C4" : "transparent" }}>
        <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 13, fontWeight: 600, width: 46, paddingTop: 2 }}>
          {aikaAvain(r) === "99:99" ? "–" : aikaAvain(r)}
        </span>
        <div style={{ flex: "1 1 300px", minWidth: 0 }}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            {r.generoitu ? <Badge color={C.ochre}>generoitu</Badge> : <Badge color={C.teal}>käsin</Badge>}
            <Badge color={C.card}>{tyyppiNimi[r.tyyppi] ?? r.tyyppi}</Badge>
            <span style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 14 }}>{r.nimi}</span>
            {r.yksin && <Badge color={C.card}>yksin</Badge>}
            {r.lukittu_kuski_id && <Badge color={C.card}>🔒 {kuskiNimi(r.lukittu_kuski_id)}</Badge>}
            {!koordOk && <Badge color={C.rust}>⚠ ei koordinaatteja</Badge>}
          </div>
          <div style={{ fontFamily: "'Archivo',sans-serif", fontSize: 12, color: C.olive, marginTop: 3 }}>
            {r.mista_osoite || "?"} → {r.mihin_osoite || "?"}
          </div>
          <div style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive, marginTop: 2 }}>
            {aikaTeksti(r)}
            {r.henkiloita !== 1 ? ` · ${r.henkiloita} hlö` : ""}
            {r.huomiot ? ` · ${r.huomiot}` : ""}
          </div>
        </div>
        <span style={{ display: "flex", gap: 6 }}>
          <Nappi variant="ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => { setLomake(lomakkeeksi(r)); setVirhe(null); }}>
            Muokkaa
          </Nappi>
          <Nappi variant="ghost" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => poista(r)}>
            ✕
          </Nappi>
        </span>
      </div>
    );
  };

  const lomakeOsio = lomake && (
    <Kortti otsikko={lomake.id ? `Muokkaa: ${lomake.nimi || "tehtävä"}` : "Uusi tehtävä"} nro="+">
      {lomake.generoitu && (
        <p style={{ ...vihje, marginTop: 0, marginBottom: 10, color: C.rust }}>
          Tämä on generoitu tehtävä. Muokkaus tallentuu, mutta seuraava ”Generoi tehtävät” korvaa sen
          uudella. Pysyvät muutokset kannattaa tehdä Pohjatiedoissa.
        </p>
      )}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div>
          <div style={pikkuLabel}>Tyyppi</div>
          <select value={lomake.tyyppi} onChange={(e) => muuta({ tyyppi: e.target.value })} style={valintaTyyli}>
            {TYYPIT.map(([k, n]) => (
              <option key={k} value={k}>
                {n}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div style={pikkuLabel}>Nimi</div>
          <Kentta value={lomake.nimi} onChange={(v) => muuta({ nimi: v })} w={220} ph="esim. Lounashaku" />
        </div>
        <div>
          <div style={pikkuLabel}>Henkilöitä</div>
          <Kentta type="number" value={lomake.henkiloita} onChange={(v) => muuta({ henkiloita: v })} w={60} />
        </div>
        <div>
          <div style={pikkuLabel}>Henkilö (yhteystieto)</div>
          <select
            value={lomake.henkilo_id}
            onChange={(e) => muuta({ henkilo_id: e.target.value })}
            style={{ ...valintaTyyli, maxWidth: 200 }}
          >
            <option value="">—</option>
            {henkilot.map((h) => (
              <option key={h.id} value={h.id}>
                {henkiloNimi(h)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 14 }}>
        <Paikka
          otsikko="Mistä"
          osoite={lomake.mista_osoite}
          lat={lomake.mista_lat}
          lon={lomake.mista_lon}
          paikat={paikat}
          onChange={({ osoite, lat, lon }) => muuta({ mista_osoite: osoite, mista_lat: lat, mista_lon: lon })}
        />
        <Paikka
          otsikko="Mihin"
          osoite={lomake.mihin_osoite}
          lat={lomake.mihin_lat}
          lon={lomake.mihin_lon}
          paikat={paikat}
          onChange={({ osoite, lat, lon }) => muuta({ mihin_osoite: osoite, mihin_lat: lat, mihin_lon: lon })}
        />
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 14 }}>
        {AIKAKENTAT.map(([k, n]) => (
          <div key={k}>
            <div style={pikkuLabel}>{n}</div>
            <Kentta type="time" value={lomake[k]} onChange={(v) => muuta({ [k]: v })} w={110} />
          </div>
        ))}
      </div>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 14, alignItems: "flex-end" }}>
        <div>
          <div style={pikkuLabel}>Lukittu kuski</div>
          <select
            value={lomake.lukittu_kuski_id}
            onChange={(e) => muuta({ lukittu_kuski_id: e.target.value })}
            style={valintaTyyli}
          >
            <option value="">— optimoija päättää —</option>
            {kuskit.map((k) => (
              <option key={k.id} value={k.id}>
                {k.nimi}
              </option>
            ))}
          </select>
        </div>
        <Ruksi checked={lomake.yksin} onChange={(v) => muuta({ yksin: v })} label="yksin (ei kimppakyytiä)" />
        <div style={{ flex: "1 1 200px" }}>
          <div style={pikkuLabel}>Huomiot</div>
          <Kentta value={lomake.huomiot} onChange={(v) => muuta({ huomiot: v })} w="100%" ph="esim. lento laskeutuu 15:25" />
        </div>
      </div>

      <div style={{ display: "flex", gap: 10, marginTop: 18 }}>
        <Nappi variant="orange" onClick={tallenna}>
          {lomake.id ? "Tallenna" : "+ Lisää tehtävä"}
        </Nappi>
        <Nappi variant="ghost" onClick={() => setLomake(null)}>
          Peruuta
        </Nappi>
      </div>
    </Kortti>
  );

  const pohjaNappi = { padding: "6px 12px", fontSize: 12 };

  return (
    <div>
      <Kortti otsikko="Tuotanto ja kuvauspäivä" nro="▲">
        {!tuotannot.length && (
          <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
            Ei tuotantoja. Luo yksi esim. <code>python -m app.seed</code> backendissä.
          </p>
        )}
        {!!tuotannot.length && (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div>
              <div style={pikkuLabel}>Tuotanto</div>
              <select value={tuotantoId} onChange={(e) => setTuotantoId(e.target.value)} style={valintaTyyli}>
                {tuotannot.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nimi}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div style={pikkuLabel}>Kuvauspäivä</div>
              <select value={paivaId} onChange={(e) => setPaivaId(e.target.value)} style={valintaTyyli}>
                <option value="">— valitse —</option>
                {paivat.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.pvm} {p.paiva_nro ? `· ${p.paiva_nro}` : ""}
                  </option>
                ))}
              </select>
            </div>
            {paiva && (
              <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: C.olive }}>
                call {aikaIn(paiva.call_time)}
                {paiva.lounas ? ` · lounas ${aikaIn(paiva.lounas)}` : ""}
                {paiva.wrap_arvio ? ` · wrap ${aikaIn(paiva.wrap_arvio)}` : ""}
              </span>
            )}
            {paiva && (
              <Nappi variant="orange" onClick={generoiTehtavat} disabled={generoi} style={{ marginLeft: "auto" }}>
                {generoi ? "Generoidaan…" : "⟳ Generoi tehtävät"}
              </Nappi>
            )}
          </div>
        )}
        {paiva && (
          <p style={vihje}>
            Generointi tekee noudot, siirtymät ja paluut Pohjatietojen perusteella. Uudelleengenerointi korvaa vain
            generoidut tehtävät — käsin lisätyt säilyvät.
          </p>
        )}
      </Kortti>

      {varoitus && (
        <div
          style={{
            border: `2px solid ${C.line}`,
            background: C.ochre,
            borderRadius: 12,
            padding: "10px 14px",
            marginBottom: 16,
            fontFamily: "'Archivo',sans-serif",
            fontWeight: 600,
            fontSize: 13,
            color: C.inkSolid,
          }}
        >
          ⚠ {varoitus}
        </div>
      )}
      {ilmoitus && !virhe && (
        <div style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 600, fontSize: 13, color: C.teal, marginBottom: 12 }}>
          ✓ {ilmoitus}
        </div>
      )}
      {virhe && (
        <div
          style={{
            border: `2px solid ${C.rust}`,
            background: "#F7DFD2",
            borderRadius: 12,
            padding: "10px 14px",
            marginBottom: 16,
            fontFamily: "'Archivo',sans-serif",
            fontWeight: 600,
            fontSize: 13,
            color: C.rust,
          }}
        >
          ⚠ {virhe}
        </div>
      )}

      {paiva && lomakeOsio}

      {paiva && (
        <Kortti
          otsikko="Päivän tehtävät"
          nro={tehtavat.length}
          lisa={ilmanKoordinaatteja ? `${ilmanKoordinaatteja} ilman koordinaatteja` : null}
        >
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 12, color: C.olive, fontWeight: 600, marginRight: 6 }}>
              {generoidut.length} generoitua · {kasin.length} käsin
            </span>
            <Nappi variant="ghost" style={pohjaNappi} onClick={() => avaaPohja("tyhja")}>
              + Uusi tehtävä
            </Nappi>
            <Nappi variant="ghost" style={pohjaNappi} onClick={() => avaaPohja("lounas")}>
              + Lounashaku
            </Nappi>
            <Nappi variant="ghost" style={pohjaNappi} onClick={() => avaaPohja("kortit")}>
              + Kortit
            </Nappi>
            <Nappi variant="ghost" style={pohjaNappi} onClick={() => avaaPohja("lento")}>
              + Lentokenttänouto
            </Nappi>
          </div>
          {!tehtavat.length && (
            <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
              Ei tehtäviä. Paina ⟳ Generoi tehtävät tai lisää käsin.
            </p>
          )}
          {jarjestetyt.map(tehtavaRivi)}
          {!!tehtavat.length && (
            <p style={vihje}>Seuraavaksi: ★ Optimointi-välilehti laskee ajolistan näistä tehtävistä.</p>
          )}
        </Kortti>
      )}
    </div>
  );
}

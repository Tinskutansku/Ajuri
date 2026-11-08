import { useEffect, useState } from "react";
import { haeKuvauspaivat, optimoiPaiva } from "./api.js";
import { C, Nappi, Kortti, pikkuLabel, kelloNyt } from "./ui.jsx";
import Tulos from "./Tulos.jsx";
import Tulostus from "./Tulostus.jsx";
import KuskitPelissa from "./KuskitPelissa.jsx";

export default function Optimointi() {
  const [paivat, setPaivat] = useState([]);
  const [paivatVirhe, setPaivatVirhe] = useState(null);
  const [paivatLadattu, setPaivatLadattu] = useState(false);
  const [valittuId, setValittuId] = useState("");

  const [tulos, setTulos] = useState(null);
  const [laskee, setLaskee] = useState(false);
  const [virhe, setVirhe] = useState(null);

  useEffect(() => {
    haeKuvauspaivat()
      .then((data) => {
        setPaivat(data);
        if (data.length) setValittuId(String(data[0].id));
      })
      .catch((e) => setPaivatVirhe(e.message))
      .finally(() => setPaivatLadattu(true));
  }, []);

  const valitsePaiva = (id) => {
    setValittuId(id);
    setTulos(null);
    setVirhe(null);
  };

  const optimoi = async (pyynto) => {
    if (!valittuId) return;
    setLaskee(true);
    setVirhe(null);
    const edellinen = tulos;
    setTulos(null);
    try {
      const data = await optimoiPaiva(Number(valittuId), pyynto);
      setTulos(data);
    } catch (e) {
      // Edellinen ajolista jää näkyviin virheen alle, ettei kiireessä
      // (esim. "pois pelistä" -reoptimointi) jää tyhjän ruudun eteen.
      setTulos(edellinen);
      setVirhe(e.message);
    } finally {
      setLaskee(false);
    }
  };

  // "Kuski pois pelistä" / "Takaisin peliin": jos ajolista on jo näkyvissä,
  // reoptimoidaan se tästä hetkestä (kuitatut ja alkaneet keikat lukitaan).
  // Skenaariovertailu jätetään pois, jotta uusi lista valmistuu nopeasti.
  const reoptimoi = () =>
    tulos
      ? optimoi({ aikaraja_s: 8, nyt: kelloNyt(), pohjaversio_id: tulos.versio_id, skenaariot: false })
      : optimoi();

  const valittuPaiva = paivat.find((p) => String(p.id) === valittuId);

  return (
    <>
      <Kortti otsikko="Kuvauspäivä" nro="1">
        {paivatVirhe && (
          <p style={{ color: C.rust, fontFamily: "'Archivo',sans-serif", fontSize: 13, fontWeight: 600 }}>
            Kuvauspäivien haku epäonnistui: {paivatVirhe}
          </p>
        )}
        {!paivatLadattu && (
          <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>Haetaan kuvauspäiviä…</p>
        )}
        {paivatLadattu && !paivatVirhe && !paivat.length && (
          <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
            Ei kuvauspäiviä. Aja esim. <code>python -m app.seed</code> backendissä.
          </p>
        )}
        {!!paivat.length && (
          <div style={{ display: "flex", gap: 14, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div>
              <div style={pikkuLabel}>Valitse päivä</div>
              <select
                value={valittuId}
                onChange={(e) => valitsePaiva(e.target.value)}
                style={{
                  fontFamily: "'IBM Plex Mono',monospace",
                  fontWeight: 600,
                  fontSize: 13,
                  padding: "8px 10px",
                  border: `2px solid ${C.line}`,
                  borderRadius: 8,
                  background: C.card,
                  color: C.inkSolid,
                  cursor: "pointer",
                }}
              >
                {paivat.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.pvm}
                    {p.paiva_nro ? ` (${p.paiva_nro})` : ""}
                  </option>
                ))}
              </select>
            </div>
            {valittuPaiva && (
              <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: C.olive }}>
                call {valittuPaiva.call_time.slice(0, 5)}
                {valittuPaiva.wrap_arvio ? ` · wrap ${valittuPaiva.wrap_arvio.slice(0, 5)}` : ""}
              </span>
            )}
            <Nappi variant="orange" onClick={() => optimoi()} disabled={laskee || !valittuId} style={{ marginLeft: "auto" }}>
              {laskee ? "Lasketaan…" : tulos ? "↻ Optimoi uudelleen" : "★ Optimoi"}
            </Nappi>
          </div>
        )}
      </Kortti>

      <KuskitPelissa paiva={valittuPaiva} onReoptimoi={reoptimoi} laskee={laskee} />

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
          ⚠ Optimointi epäonnistui: {virhe}
        </div>
      )}

      {tulos && <Tulostus tulos={tulos} paiva={valittuPaiva} />}
      {tulos && <Tulos tulos={tulos} />}

      {!tulos && !laskee && !virhe && (
        <div style={{ textAlign: "center", padding: "60px 20px", fontFamily: "'Archivo',sans-serif", color: C.olive, fontWeight: 600 }}>
          Valitse päivä ja paina ★ Optimoi.
        </div>
      )}
      {laskee && (
        <div style={{ textAlign: "center", padding: "60px 20px", fontFamily: "'Archivo',sans-serif", color: C.olive, fontWeight: 600 }}>
          Lasketaan… OR-Tools + OSRM voivat viedä hetken.
          <div style={{ fontWeight: 400, fontSize: 13, marginTop: 8 }}>
            Mukana skenaariovertailu (montako kuskia kannattaa ottaa): yksi ratkaisu jokaiselle kuskimäärälle,
            joten tämä vie noin 10 s jokaista päivän kuskia kohden (5 kuskilla noin minuutin). Muut
            välilehdet toimivat sillä välin, ja sivun voi päivittää: laskenta jatkuu backendissä.
          </div>
        </div>
      )}
    </>
  );
}

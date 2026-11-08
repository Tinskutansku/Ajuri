/* "Kuski pois pelistä" -hätänappi (ROADMAP I2, docs/tuotekartta.md vaihe I).

   Yksi painallus tekee kaksi olemassa olevaa kutsua peräkkäin:
   1) PUT /paiva-kuskit/{id} tarjolla=false (tai takaisin true)
   2) POST /paivat/{id}/optimoi nyt=<kellonaika nyt>, pohjaversio_id=<näkyvä versio>

   Reoptimointi lukitsee kuitatut ja jo alkaneet (nouto ennen nyt-hetkeä)
   keikat ennalleen, ja loput jaetaan pelissä oleville kuskeille. Jos
   ajolistaa ei vielä ole, optimoidaan koko päivä. */
import { useEffect, useState } from "react";
import { haeKuskit, haePaivaKuskit, paivitaPaivaKuski } from "./api.js";
import { C, Kortti, Nappi, Badge, riviTyyli, vihje, kelloNyt } from "./ui.jsx";

export default function KuskitPelissa({ paiva, onReoptimoi, laskee }) {
  const [rivit, setRivit] = useState([]);
  const [nimet, setNimet] = useState({});
  const [virhe, setVirhe] = useState(null);
  const [kasittelyssa, setKasittelyssa] = useState(null);

  useEffect(() => {
    if (!paiva) return;
    let peruttu = false;
    Promise.all([haePaivaKuskit(paiva.id), haeKuskit(paiva.tuotanto_id)])
      .then(([paivaKuskit, kuskit]) => {
        if (peruttu) return;
        setVirhe(null);
        setRivit(paivaKuskit);
        setNimet(Object.fromEntries(kuskit.map((k) => [k.id, k.nimi])));
      })
      .catch((e) => !peruttu && setVirhe(e.message));
    return () => {
      peruttu = true;
    };
  }, [paiva]);

  const vaihda = async (rivi) => {
    const tarjolla = !rivi.tarjolla;
    setKasittelyssa(rivi.id);
    setVirhe(null);
    try {
      const { id, ...data } = rivi;
      const paivitetty = await paivitaPaivaKuski(id, { ...data, tarjolla });
      setRivit((vanhat) => vanhat.map((r) => (r.id === id ? paivitetty : r)));
      await onReoptimoi();
    } catch (e) {
      setVirhe(e.message);
    } finally {
      setKasittelyssa(null);
    }
  };

  if (!paiva) return null;

  return (
    <Kortti otsikko="Kuskit tänään" nro="2">
      {virhe && (
        <p style={{ color: C.rust, fontFamily: "'Archivo',sans-serif", fontSize: 13, fontWeight: 600 }}>⚠ {virhe}</p>
      )}
      {!rivit.length && !virhe && (
        <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
          Päivälle ei ole lisätty kuskeja (Pohjatiedot-välilehti).
        </p>
      )}
      {rivit.map((r) => (
        <div key={r.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
          <span
            style={{
              fontFamily: "'Archivo',sans-serif",
              fontWeight: 600,
              fontSize: 13,
              textDecoration: r.tarjolla ? "none" : "line-through",
              color: r.tarjolla ? C.inkSolid : C.olive,
            }}
          >
            {nimet[r.kuski_id] ?? `Kuski ${r.kuski_id}`}
          </span>
          {r.tarjolla ? <Badge color={C.teal}>PELISSÄ</Badge> : <Badge color={C.rust}>POIS PELISTÄ</Badge>}
          <Nappi
            variant={r.tarjolla ? "ink" : "ghost"}
            onClick={() => vaihda(r)}
            disabled={laskee || kasittelyssa !== null}
            style={{ marginLeft: "auto", fontSize: 12, padding: "6px 14px" }}
          >
            {kasittelyssa === r.id ? "Lasketaan…" : r.tarjolla ? "⛔ Pois pelistä" : "↩ Takaisin peliin"}
          </Nappi>
        </div>
      ))}
      <p style={vihje}>
        Nappi vaihtaa kuskin tilan ja laskee ajolistan heti uudelleen tästä hetkestä ({kelloNyt()}). Kuitatut ja jo
        alkaneet keikat pysyvät ennallaan, loput jaetaan pelissä oleville kuskeille.
      </p>
    </Kortti>
  );
}

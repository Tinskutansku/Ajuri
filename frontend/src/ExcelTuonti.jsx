/* Excel-tuonti Rekisteriin (ROADMAP O2).

   Kulku: valitse xlsx → esikatselu (backend tulkitsee, ei tallenna) →
   "Tuo N henkilöä" (backend tulkitsee saman tiedoston uudelleen ja
   tallentaa kelvolliset rivit) → koordinaattien haku erissä.

   Tallennus lähettää saman tiedoston uudelleen eikä esikatselun tulosta,
   joten backend ei luota selaimessa muokattuun dataan. */

import { useRef, useState } from "react";
import { C, Kortti, Nappi, Badge, pikkuLabel, vihje } from "./ui.jsx";
import * as api from "./api.js";

const POHJA_URL = `${import.meta.env.BASE_URL}henkilot-pohja.xlsx`;
const GEOKOODAUS_ERIA_MAX = 40; // 40 × 15 osoitetta riittää tuonnin 500 riville

const teksti = { fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.inkSolid, margin: "6px 0" };
const solu = {
  padding: "6px 8px",
  borderBottom: `1px solid ${C.ink}`,
  verticalAlign: "top",
  textAlign: "left",
};

function Ilmoitus({ vari, tausta, children }) {
  return (
    <div
      role="status"
      style={{
        border: `2px solid ${vari}`,
        background: tausta,
        borderRadius: 12,
        padding: "10px 14px",
        margin: "10px 0",
        fontFamily: "'Archivo',sans-serif",
        fontWeight: 600,
        fontSize: 13,
        color: C.inkSolid,
      }}
    >
      {children}
    </div>
  );
}

export default function ExcelTuonti({ tuotantoId, onTuotu }) {
  const syoteRef = useRef(null);
  const [tiedosto, setTiedosto] = useState(null);
  const [esikatselu, setEsikatselu] = useState(null);
  const [tulos, setTulos] = useState(null);
  const [geo, setGeo] = useState(null); // { kaynnissa, paivitetty, epaonnistui, jaljella }
  const [kaynnissa, setKaynnissa] = useState(false);
  const [virhe, setVirhe] = useState(null);

  const nollaa = () => {
    setTiedosto(null);
    setEsikatselu(null);
    setVirhe(null);
    if (syoteRef.current) syoteRef.current.value = "";
  };

  const valitseTiedosto = async (e) => {
    const valittu = e.target.files?.[0];
    setTulos(null);
    setGeo(null);
    setEsikatselu(null);
    setVirhe(null);
    setTiedosto(valittu || null);
    if (!valittu) return;
    setKaynnissa(true);
    try {
      setEsikatselu(await api.esikatseleTuonti(tuotantoId, valittu));
    } catch (err) {
      setVirhe(err.message);
    } finally {
      setKaynnissa(false);
    }
  };

  const vahvista = async () => {
    if (!tiedosto) return;
    setKaynnissa(true);
    setVirhe(null);
    try {
      const vastaus = await api.tallennaTuonti(tuotantoId, tiedosto);
      setTulos(vastaus);
      nollaa();
      onTuotu?.();
    } catch (err) {
      setVirhe(err.message);
    } finally {
      setKaynnissa(false);
    }
  };

  // Nominatim sallii 1 kutsun/s, joten backend käsittelee kerralla vain
  // erän. Kutsutaan uudestaan, kunnes jäljellä on 0 tai mikään ei etene.
  const haeKoordinaatit = async () => {
    let paivitetty = 0;
    let epaonnistui = 0;
    setVirhe(null);
    setGeo({ kaynnissa: true, paivitetty, epaonnistui, jaljella: null });
    try {
      for (let era = 0; era < GEOKOODAUS_ERIA_MAX; era++) {
        const v = await api.geokoodaaTuotanto(tuotantoId);
        const eranPaivitetyt = v.henkilot_paivitetty + v.kuskit_paivitetty + v.lokaatiot_paivitetty;
        const eranEpaonnistuneet = v.henkilot_epaonnistui + v.kuskit_epaonnistui + v.lokaatiot_epaonnistui;
        paivitetty += eranPaivitetyt;
        epaonnistui += eranEpaonnistuneet;
        setGeo({ kaynnissa: true, paivitetty, epaonnistui, jaljella: v.jaljella });
        if (v.jaljella === 0 || eranPaivitetyt + eranEpaonnistuneet === 0) break;
      }
      setGeo((g) => ({ ...g, kaynnissa: false }));
    } catch (err) {
      setVirhe(err.message);
      setGeo((g) => ({ ...g, kaynnissa: false }));
    } finally {
      onTuotu?.();
    }
  };

  const tunnistetut = esikatselu?.sarakkeet.filter((s) => s.otsikko) ?? [];

  return (
    <Kortti otsikko="Tuo Excelistä" nro="⇪">
      <p style={{ ...teksti, color: C.olive }}>
        Tuo näyttelijät ja työryhmä xlsx-tiedostosta. Ensimmäinen välilehti luetaan, otsikkorivi tunnistetaan
        automaattisesti. Esikatselu ei vielä tallenna mitään.
      </p>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
        <label
          htmlFor="tuonti-tiedosto"
          style={{
            fontFamily: "'Archivo',sans-serif",
            fontWeight: 700,
            fontSize: 14,
            padding: "10px 18px",
            borderRadius: 999,
            border: `2px solid ${C.line}`,
            background: C.inkSolid,
            color: C.card,
            boxShadow: `3px 3px 0 ${C.line}`,
            cursor: kaynnissa ? "not-allowed" : "pointer",
            opacity: kaynnissa ? 0.5 : 1,
          }}
        >
          Valitse Excel-tiedosto…
        </label>
        <input
          id="tuonti-tiedosto"
          ref={syoteRef}
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={valitseTiedosto}
          disabled={kaynnissa}
          style={{ position: "absolute", width: 1, height: 1, opacity: 0 }}
        />
        <a
          href={POHJA_URL}
          download="AJURI-henkilot-pohja.xlsx"
          style={{ fontFamily: "'Archivo',sans-serif", fontWeight: 700, fontSize: 13, color: C.teal }}
        >
          ⤓ Lataa pohjatiedosto
        </a>
        {tiedosto && (
          <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 12, color: C.inkSolid }}>
            {tiedosto.name}
          </span>
        )}
        {kaynnissa && <span style={{ ...teksti, color: C.olive }}>Käsitellään…</span>}
      </div>

      {virhe && (
        <Ilmoitus vari={C.rust} tausta="#F7DFD2">
          ⚠ {virhe}
        </Ilmoitus>
      )}

      {tulos && (
        <Ilmoitus vari={C.teal} tausta="#DCE8E3">
          ✓ Tallennettu {tulos.tallennettu} henkilöä.
          {tulos.ohitetut_rivit.length > 0 &&
            (tulos.ohitetut_rivit.length === 1
              ? ` Ohitettiin 1 virheellinen rivi (rivi ${tulos.ohitetut_rivit[0]}).`
              : ` Ohitettiin ${tulos.ohitetut_rivit.length} virheellistä riviä (rivit ${tulos.ohitetut_rivit.join(", ")}).`)}
          {tulos.geokoodaamatta > 0 && (
            <div style={{ marginTop: 8, display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ fontWeight: 500 }}>
                {tulos.geokoodaamatta} osoitteelta puuttuu vielä koordinaatit. Optimointi tarvitsee ne.
              </span>
              <Nappi variant="orange" onClick={haeKoordinaatit} disabled={geo?.kaynnissa}>
                {geo?.kaynnissa ? "Haetaan koordinaatteja…" : "Hae koordinaatit"}
              </Nappi>
            </div>
          )}
          {geo && (
            <div style={{ marginTop: 6, fontWeight: 500 }}>
              Koordinaatit löytyivät {geo.paivitetty} osoitteelle
              {geo.epaonnistui > 0 && `, ${geo.epaonnistui} osoitetta ei löytynyt (korjaa ne käsin listassa)`}
              {geo.kaynnissa && geo.jaljella != null && `, jäljellä ${geo.jaljella}`}
              {!geo.kaynnissa && "."}
            </div>
          )}
        </Ilmoitus>
      )}

      {esikatselu && (
        <div style={{ marginTop: 12 }}>
          <div style={pikkuLabel}>Tunnistetut sarakkeet</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {tunnistetut.map((s, i) => (
              <Badge key={`${s.otsikko}-${i}`} color={s.kentta ? C.ochre : C.card}>
                {s.otsikko}
                {s.kentta ? ` → ${s.kentta}` : " (ei käytetä)"}
              </Badge>
            ))}
          </div>

          <p style={{ ...teksti, fontWeight: 700 }}>
            {esikatselu.kelvollisia} kelvollista riviä
            {esikatselu.virheellisia > 0 && (
              <span style={{ color: C.rust }}> · {esikatselu.virheellisia} virheellistä ohitetaan</span>
            )}
          </p>

          <div style={{ overflowX: "auto", maxHeight: 420, overflowY: "auto", border: `2px solid ${C.line}`, borderRadius: 10 }}>
            <table
              style={{
                borderCollapse: "collapse",
                width: "100%",
                fontFamily: "'Archivo',sans-serif",
                fontSize: 12,
                color: C.inkSolid,
                background: C.card,
              }}
            >
              <thead style={{ position: "sticky", top: 0, background: C.paper }}>
                <tr>
                  {["Rivi", "Nimi", "Tyyppi", "Rooli / titteli", "Puhelin", "Osoite", "Huomiot"].map((o) => (
                    <th key={o} scope="col" style={{ ...solu, ...pikkuLabel, marginBottom: 0 }}>
                      {o}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {esikatselu.rivit.map((r) => {
                  const h = r.henkilo;
                  const virheellinen = r.virheet.length > 0;
                  return (
                    <tr key={r.rivi} style={{ background: virheellinen ? "#F7DFD2" : undefined }}>
                      <td style={{ ...solu, fontFamily: "'IBM Plex Mono',monospace" }}>{r.rivi}</td>
                      {virheellinen ? (
                        <td colSpan={6} style={{ ...solu, color: C.rust, fontWeight: 600 }}>
                          ⚠ Ohitetaan: {r.virheet.join(" ")}
                        </td>
                      ) : (
                        <>
                          <td style={{ ...solu, fontWeight: 700, minWidth: 150 }}>
                            {h.nimi}
                            {r.varoitukset.map((v) => (
                              <div key={v} style={{ color: C.olive, fontWeight: 500, fontSize: 11 }}>
                                ⓘ {v}
                              </div>
                            ))}
                          </td>
                          <td style={solu}>{h.tyyppi}</td>
                          <td style={solu}>{h.tyyppi === "cast" ? h.roolinimi : h.titteli}</td>
                          <td style={{ ...solu, fontFamily: "'IBM Plex Mono',monospace" }}>{h.puhelin}</td>
                          <td style={solu}>{h.osoite}</td>
                          <td style={solu}>{h.huomiot}</td>
                        </>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div style={{ display: "flex", gap: 12, marginTop: 14, flexWrap: "wrap" }}>
            <Nappi variant="orange" onClick={vahvista} disabled={kaynnissa || esikatselu.kelvollisia === 0}>
              Tuo {esikatselu.kelvollisia} henkilöä
            </Nappi>
            <Nappi variant="ghost" onClick={nollaa} disabled={kaynnissa}>
              Peru
            </Nappi>
          </div>
          <p style={vihje}>
            Samannimiset tallennetaan silti erillisinä henkilöinä (kaimoja on oikeasti). Poista tuplat
            tarvittaessa listasta tuonnin jälkeen.
          </p>
        </div>
      )}
    </Kortti>
  );
}

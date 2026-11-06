import { useEffect, useRef, useState } from "react";
import { C, Kortti, Nappi, Kentta, Ruksi, Badge, riviTyyli, pikkuLabel, vihje, SOPIMUS_NIMI } from "./ui.jsx";
import * as api from "./api.js";
import OsoiteKentta from "./OsoiteKentta.jsx";

const naytaNumero = (v) => (v == null ? "" : String(v));
const parsiNumero = (s) => (String(s).trim() === "" ? null : Number(s));
const NUMEROKENTAT_KUSKI = new Set(["tuntihinta_eur", "pickup_bufferi_min"]);

const KoordinaattiMerkki = ({ lat, lon }) =>
  lat == null || lon == null ? <Badge color={C.rust}>ei koordinaatteja</Badge> : null;

// Kuskin numerokentät (tuntihinta_eur, pickup_bufferi_min) pidetään
// paikallisessa tilassa merkkijonoina editoinnin ajan (esim. "22.5"
// pysyy kirjoitettaessa, ei pyöristy heti "22":ksi) - muunnetaan takaisin
// numeroiksi vasta tallennettaessa (ks. kuskiPayload).
const muotoileKuski = (k) => ({
  ...k,
  tuntihinta_eur: naytaNumero(k.tuntihinta_eur),
  pickup_bufferi_min: naytaNumero(k.pickup_bufferi_min),
});

const kuskiPayload = (k) => {
  const { id: _id, _uusi, ...runko } = k;
  return {
    ...runko,
    tuntihinta_eur: parsiNumero(k.tuntihinta_eur),
    pickup_bufferi_min: parsiNumero(k.pickup_bufferi_min) ?? 0,
  };
};

let seuraavaTempId = -1;

export default function Rekisteri() {
  const [tuotannot, setTuotannot] = useState([]);
  const [tuotantoVirhe, setTuotantoVirhe] = useState(null);
  const [tuotantoId, setTuotantoId] = useState("");
  const [henkilot, setHenkilot] = useState([]);
  const [kuskit, setKuskit] = useState([]);
  const [virhe, setVirhe] = useState(null);

  // Viimeksi palvelimelta saatu/tallennettu tila per rivi (id -> raakarivi),
  // jotta blur voi verrata "muuttuiko oikeasti" eikä tallenna turhaan.
  const tallennettuHenkiloRef = useRef({});
  const tallennettuKuskiRef = useRef({});

  useEffect(() => {
    api
      .haeTuotannot()
      .then((d) => {
        setTuotannot(d);
        if (d.length) setTuotantoId(String(d[0].id));
      })
      .catch((e) => setTuotantoVirhe(e.message));
  }, []);

  useEffect(() => {
    if (!tuotantoId) return;
    api
      .haeHenkilot(tuotantoId)
      .then((hs) => {
        setHenkilot(hs);
        tallennettuHenkiloRef.current = Object.fromEntries(hs.map((h) => [h.id, h]));
      })
      .catch((e) => setVirhe(e.message));
    api
      .haeKuskit(tuotantoId)
      .then((ks) => {
        setKuskit(ks.map(muotoileKuski));
        tallennettuKuskiRef.current = Object.fromEntries(ks.map((k) => [k.id, k]));
      })
      .catch((e) => setVirhe(e.message));
  }, [tuotantoId]);

  // --- Henkilöt ---
  const muutaHenkiloPaikallisesti = (id, patch) =>
    setHenkilot((hs) => hs.map((h) => (h.id === id ? { ...h, ...patch } : h)));

  const lisaaHenkilo = (tyyppi) => {
    const uusi = {
      id: seuraavaTempId--,
      _uusi: true,
      tuotanto_id: Number(tuotantoId),
      tyyppi,
      nimi: "",
      roolinimi: "",
      titteli: "",
      osoite: "",
      puhelin: "",
      oletus_oma_auto: false,
      oletus_yksin: false,
      lat: null,
      lon: null,
    };
    setHenkilot((hs) => [...hs, uusi]);
  };

  const henkiloNimiBlur = async (h) => {
    if (h._uusi) {
      if (!h.nimi.trim()) return; // ei tallenneta tyhjänä nimenä
      try {
        const { id: _id, _uusi, ...runko } = h;
        const luotu = await api.luoHenkilo(runko);
        setHenkilot((hs) => hs.map((x) => (x.id === h.id ? luotu : x)));
        tallennettuHenkiloRef.current[luotu.id] = luotu;
      } catch (e) {
        setVirhe(e.message);
      }
      return;
    }
    henkiloBlur(h, "nimi");
  };

  const henkiloBlur = async (h, kentta) => {
    if (h._uusi) return; // ei vielä palvelimella
    const tallennettu = tallennettuHenkiloRef.current[h.id];
    if (tallennettu && tallennettu[kentta] === h[kentta]) return; // ei muuttunut
    try {
      const { id: _id, ...runko } = h;
      const paivitetty = await api.paivitaHenkilo(h.id, runko);
      setHenkilot((hs) => hs.map((x) => (x.id === h.id ? paivitetty : x)));
      tallennettuHenkiloRef.current[h.id] = paivitetty;
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const henkiloAsetaHeti = async (h, patch) => {
    muutaHenkiloPaikallisesti(h.id, patch);
    if (h._uusi) return;
    try {
      const { id: _id, ...runko } = { ...h, ...patch };
      const paivitetty = await api.paivitaHenkilo(h.id, runko);
      tallennettuHenkiloRef.current[h.id] = paivitetty;
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const poistaHenkiloRivi = async (h) => {
    if (h._uusi) {
      setHenkilot((hs) => hs.filter((x) => x.id !== h.id));
      return;
    }
    let viesti = `Poistetaanko ${h.nimi || "henkilö"}?`;
    try {
      const kaytto = await api.haeHenkiloKaytto(h.id);
      if (kaytto.length) {
        const paivat = kaytto.map((k) => k.paiva_nro || k.pvm).join(", ");
        viesti =
          `${h.nimi || "Henkilö"} on mukana ${kaytto.length} kuvauspäivässä (${paivat}). ` +
          `Poistaminen piilottaa hänet listoilta, mutta vanhat ajolistat säilyvät ennallaan. Poistetaanko?`;
      }
    } catch (e) {
      setVirhe(e.message);
      return;
    }
    if (!window.confirm(viesti)) return;
    try {
      await api.poistaHenkilo(h.id);
      setHenkilot((hs) => hs.filter((x) => x.id !== h.id));
      delete tallennettuHenkiloRef.current[h.id];
    } catch (e) {
      setVirhe(e.message);
    }
  };

  // --- Kuskit ---
  const muutaKuskiPaikallisesti = (id, patch) =>
    setKuskit((ks) => ks.map((k) => (k.id === id ? { ...k, ...patch } : k)));

  const lisaaKuski = () => {
    const uusi = {
      id: seuraavaTempId--,
      _uusi: true,
      tuotanto_id: Number(tuotantoId),
      nimi: "",
      puhelin: "",
      sopimus: "kuukausi",
      tuntihinta_eur: "",
      koti_osoite: "",
      koti_lat: null,
      koti_lon: null,
      pickup_bufferi_min: "0",
    };
    setKuskit((ks) => [...ks, uusi]);
  };

  const kuskiNimiBlur = async (k) => {
    if (k._uusi) {
      if (!k.nimi.trim()) return;
      try {
        const luotu = await api.luoKuski(kuskiPayload(k));
        setKuskit((ks) => ks.map((x) => (x.id === k.id ? muotoileKuski(luotu) : x)));
        tallennettuKuskiRef.current[luotu.id] = luotu;
      } catch (e) {
        setVirhe(e.message);
      }
      return;
    }
    kuskiBlur(k, "nimi");
  };

  const kuskiBlur = async (k, kentta) => {
    if (k._uusi) return;
    const tallennettu = tallennettuKuskiRef.current[k.id];
    const nykyinen = NUMEROKENTAT_KUSKI.has(kentta) ? parsiNumero(k[kentta]) : k[kentta];
    if (tallennettu && tallennettu[kentta] === nykyinen) return; // ei muuttunut
    try {
      const paivitetty = await api.paivitaKuski(k.id, kuskiPayload(k));
      setKuskit((ks) => ks.map((x) => (x.id === k.id ? muotoileKuski(paivitetty) : x)));
      tallennettuKuskiRef.current[k.id] = paivitetty;
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const kuskiAsetaHeti = async (k, patch) => {
    muutaKuskiPaikallisesti(k.id, patch);
    if (k._uusi) return;
    try {
      const paivitetty = await api.paivitaKuski(k.id, kuskiPayload({ ...k, ...patch }));
      tallennettuKuskiRef.current[k.id] = paivitetty;
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const poistaKuskiRivi = async (k) => {
    if (k._uusi) {
      setKuskit((ks) => ks.filter((x) => x.id !== k.id));
      return;
    }
    let viesti = `Poistetaanko ${k.nimi || "kuski"}?`;
    try {
      const kaytto = await api.haeKuskiKaytto(k.id);
      if (kaytto.length) {
        const paivat = kaytto.map((p) => p.paiva_nro || p.pvm).join(", ");
        viesti =
          `${k.nimi || "Kuski"} on mukana ${kaytto.length} kuvauspäivässä (${paivat}). ` +
          `Poistaminen piilottaa hänet listoilta, mutta vanhat ajolistat säilyvät ennallaan. Poistetaanko?`;
      }
    } catch (e) {
      setVirhe(e.message);
      return;
    }
    if (!window.confirm(viesti)) return;
    try {
      await api.poistaKuski(k.id);
      setKuskit((ks) => ks.filter((x) => x.id !== k.id));
      delete tallennettuKuskiRef.current[k.id];
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const ryhma = (tyyppi, otsikko, nro) => (
    <Kortti otsikko={otsikko} nro={nro}>
      {henkilot
        .filter((h) => h.tyyppi === tyyppi)
        .map((h) => (
          <div key={h.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
            <Kentta
              value={h.nimi}
              onChange={(v) => muutaHenkiloPaikallisesti(h.id, { nimi: v })}
              onBlur={() => henkiloNimiBlur(h)}
              w={150}
              ph="Nimi"
            />
            {tyyppi === "cast" ? (
              <Kentta
                value={h.roolinimi || ""}
                onChange={(v) => muutaHenkiloPaikallisesti(h.id, { roolinimi: v })}
                onBlur={() => henkiloBlur(h, "roolinimi")}
                w={120}
                ph="Roolinimi"
              />
            ) : (
              <Kentta
                value={h.titteli || ""}
                onChange={(v) => muutaHenkiloPaikallisesti(h.id, { titteli: v })}
                onBlur={() => henkiloBlur(h, "titteli")}
                w={120}
                ph="Titteli"
              />
            )}
            <OsoiteKentta
              value={h.osoite || ""}
              // Käsin muutettu osoite: koordinaatit pois pyynnöstä (undefined
              // putoaa JSONista), jotta backend geokoodaa uuden osoitteen eikä
              // säilytä vanhoja koordinaatteja "käsin annettuina".
              onChange={(v) => muutaHenkiloPaikallisesti(h.id, { osoite: v, lat: undefined, lon: undefined })}
              onValitse={(e) => henkiloAsetaHeti(h, { osoite: e.nimi, lat: e.lat, lon: e.lon })}
              onBlur={() => henkiloBlur(h, "osoite")}
              w={160}
              ph="Osoite"
            />
            <Kentta
              value={h.puhelin || ""}
              onChange={(v) => muutaHenkiloPaikallisesti(h.id, { puhelin: v })}
              onBlur={() => henkiloBlur(h, "puhelin")}
              w={110}
              ph="Puhelin"
            />
            <KoordinaattiMerkki lat={h.lat} lon={h.lon} />
            <span style={{ marginLeft: "auto", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              <Ruksi
                checked={h.oletus_oma_auto}
                onChange={(v) => henkiloAsetaHeti(h, { oletus_oma_auto: v })}
                label="oma auto"
              />
              <Ruksi
                checked={h.oletus_yksin}
                onChange={(v) => henkiloAsetaHeti(h, { oletus_yksin: v })}
                label="ei kimppakyytejä"
              />
              <button
                onClick={() => poistaHenkiloRivi(h)}
                style={{ border: "none", background: "none", cursor: "pointer", color: C.rust, fontWeight: 900, fontSize: 16 }}
              >
                ×
              </button>
            </span>
          </div>
        ))}
      <div style={{ marginTop: 12 }}>
        <Nappi variant="ghost" onClick={() => lisaaHenkilo(tyyppi)}>
          + Lisää {tyyppi === "cast" ? "näyttelijä" : "työryhmäläinen"}
        </Nappi>
      </div>
    </Kortti>
  );

  return (
    <div>
      <Kortti otsikko="Tuotanto" nro="◆">
        {tuotantoVirhe && (
          <p style={{ color: C.rust, fontFamily: "'Archivo',sans-serif", fontSize: 13, fontWeight: 600 }}>
            Tuotantojen haku epäonnistui: {tuotantoVirhe}
          </p>
        )}
        {!tuotantoVirhe && !tuotannot.length && (
          <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
            Ei tuotantoja. Luo yksi esim. <code>python -m app.seed</code> backendissä tai
            Swaggerin (<code>/docs</code>) <code>POST /tuotannot</code> kautta.
          </p>
        )}
        {!!tuotannot.length && (
          <div>
            <div style={pikkuLabel}>Valitse tuotanto</div>
            <select
              value={tuotantoId}
              onChange={(e) => setTuotantoId(e.target.value)}
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
              {tuotannot.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.nimi}
                </option>
              ))}
            </select>
          </div>
        )}
      </Kortti>

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

      {!!tuotantoId && (
        <>
          {ryhma("cast", "Näyttelijät", "A")}
          {ryhma("crew", "Työryhmä", "B")}

          <Kortti otsikko="Kuskit" nro="C">
            {kuskit.map((k) => (
              <div key={k.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
                <Kentta
                  value={k.nimi}
                  onChange={(v) => muutaKuskiPaikallisesti(k.id, { nimi: v })}
                  onBlur={() => kuskiNimiBlur(k)}
                  w={130}
                  ph="Nimi"
                />
                <Kentta
                  value={k.puhelin || ""}
                  onChange={(v) => muutaKuskiPaikallisesti(k.id, { puhelin: v })}
                  onBlur={() => kuskiBlur(k, "puhelin")}
                  w={110}
                  ph="Puhelin"
                />
                <select
                  value={k.sopimus}
                  onChange={(e) => kuskiAsetaHeti(k, { sopimus: e.target.value })}
                  style={{
                    fontFamily: "'Archivo',sans-serif",
                    fontWeight: 600,
                    fontSize: 12,
                    padding: "6px 8px",
                    border: `2px solid ${C.line}`,
                    borderRadius: 8,
                    background: C.card,
                    color: C.inkSolid,
                    cursor: "pointer",
                  }}
                >
                  {Object.entries(SOPIMUS_NIMI).map(([arvo, nimi]) => (
                    <option key={arvo} value={arvo}>
                      {nimi}
                    </option>
                  ))}
                </select>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={pikkuLabel}>€/h</span>
                  <Kentta
                    type="number"
                    value={k.tuntihinta_eur}
                    onChange={(v) => muutaKuskiPaikallisesti(k.id, { tuntihinta_eur: v })}
                    onBlur={() => kuskiBlur(k, "tuntihinta_eur")}
                    w={72}
                    ph="tuot. oletus"
                  />
                </span>
                <OsoiteKentta
                  value={k.koti_osoite || ""}
                  onChange={(v) =>
                    muutaKuskiPaikallisesti(k.id, { koti_osoite: v, koti_lat: undefined, koti_lon: undefined })
                  }
                  onValitse={(e) => kuskiAsetaHeti(k, { koti_osoite: e.nimi, koti_lat: e.lat, koti_lon: e.lon })}
                  onBlur={() => kuskiBlur(k, "koti_osoite")}
                  w={160}
                  ph="Kotiosoite"
                />
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={pikkuLabel}>pickup-bufferi</span>
                  <Kentta
                    type="number"
                    value={k.pickup_bufferi_min}
                    onChange={(v) => muutaKuskiPaikallisesti(k.id, { pickup_bufferi_min: v })}
                    onBlur={() => kuskiBlur(k, "pickup_bufferi_min")}
                    w={44}
                  />
                  <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive }}>min</span>
                </span>
                <KoordinaattiMerkki lat={k.koti_lat} lon={k.koti_lon} />
                <button
                  onClick={() => poistaKuskiRivi(k)}
                  style={{ marginLeft: "auto", border: "none", background: "none", cursor: "pointer", color: C.rust, fontWeight: 900, fontSize: 16 }}
                >
                  ×
                </button>
              </div>
            ))}
            <div style={{ marginTop: 12 }}>
              <Nappi variant="ghost" onClick={lisaaKuski}>
                + Lisää kuski
              </Nappi>
            </div>
          </Kortti>

          <p style={vihje}>
            Koordinaatteja ei syötetä käsin — ne haetaan automaattisesti osoitteesta kun rivi
            tallennetaan. "Ei koordinaatteja" -merkki katoaa kun geokoodaus on onnistunut (tai
            pysyy jos osoitetta ei löytynyt / osoite puuttuu).
          </p>
        </>
      )}
    </div>
  );
}

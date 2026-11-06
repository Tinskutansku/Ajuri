import { useEffect, useRef, useState } from "react";
import { C, Kortti, Nappi, Kentta, Ruksi, Badge, riviTyyli, pikkuLabel, vihje } from "./ui.jsx";
import * as api from "./api.js";
import OsoiteKentta from "./OsoiteKentta.jsx";

/* Pohjatiedot — kuvauspäivän kokoaminen: päivän ajat, lokaatiot,
   ketkä ovat mukana ja ketkä kuskit ajavat. Kaikki rivit ovat
   päiväkohtaisia (paiva_*-taulut); rekisterin perusdataan ei kosketa. */

// Backend palauttaa ajat muodossa "HH:MM:SS", <input type="time"> haluaa
// "HH:MM". Tyhjä kenttä tallentuu null:ina, ei tyhjänä merkkijonona.
const aikaIn = (v) => (v ? String(v).slice(0, 5) : "");
const aikaOut = (v) => {
  const s = String(v ?? "").trim();
  return s === "" ? null : s;
};

const muotoilePaiva = (p) => ({
  ...p,
  call_time: aikaIn(p.call_time),
  lounas: aikaIn(p.lounas),
  wrap_arvio: aikaIn(p.wrap_arvio),
});
const paivaPayload = (p) => ({
  tuotanto_id: p.tuotanto_id,
  pvm: p.pvm,
  paiva_nro: p.paiva_nro || null,
  call_time: aikaOut(p.call_time),
  lounas: aikaOut(p.lounas),
  wrap_arvio: aikaOut(p.wrap_arvio),
  huomiot: p.huomiot ?? null,
});

const muotoilePL = (r) => ({ ...r, siirtyma_klo: aikaIn(r.siirtyma_klo) });
const plPayload = (r) => ({
  paiva_id: r.paiva_id,
  lokaatio_id: Number(r.lokaatio_id),
  jarjestys: Number(r.jarjestys) || 1,
  siirtyma_klo: aikaOut(r.siirtyma_klo),
});

const muotoilePH = (r) => ({
  ...r,
  oma_call: aikaIn(r.oma_call),
  siirtyma_klo: aikaIn(r.siirtyma_klo),
});
const phPayload = (r) => ({
  paiva_id: r.paiva_id,
  henkilo_id: r.henkilo_id,
  oma_call: aikaOut(r.oma_call),
  oma_auto: r.oma_auto,
  ei_paluuta: r.ei_paluuta,
  siirtyy: r.siirtyy,
  siirtyma_klo: aikaOut(r.siirtyma_klo),
  huomiot: r.huomiot ?? null,
});

const muotoilePK = (r) => ({
  ...r,
  vuoro_aikaisintaan: aikaIn(r.vuoro_aikaisintaan),
  vuoro_viimeistaan: aikaIn(r.vuoro_viimeistaan),
  toteutunut_alku: aikaIn(r.toteutunut_alku),
  toteutunut_loppu: aikaIn(r.toteutunut_loppu),
});
const pkPayload = (r) => ({
  paiva_id: r.paiva_id,
  kuski_id: r.kuski_id,
  ajoneuvo_id: r.ajoneuvo_id ?? null,
  tarjolla: r.tarjolla,
  vuoro_aikaisintaan: aikaOut(r.vuoro_aikaisintaan),
  vuoro_viimeistaan: aikaOut(r.vuoro_viimeistaan),
  toteutunut_alku: aikaOut(r.toteutunut_alku),
  toteutunut_loppu: aikaOut(r.toteutunut_loppu),
});

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

const tanaan = () => new Date().toISOString().slice(0, 10);

const henkiloNimi = (h) =>
  h.tyyppi === "cast" && h.roolinimi ? `${h.nimi} (${h.roolinimi})` : h.nimi;

export default function Pohjatiedot() {
  const [tuotannot, setTuotannot] = useState([]);
  const [tuotantoId, setTuotantoId] = useState("");
  const [paivat, setPaivat] = useState([]);
  const [paivaId, setPaivaId] = useState("");
  const [paiva, setPaiva] = useState(null);

  const [lokaatiot, setLokaatiot] = useState([]);
  const [henkilot, setHenkilot] = useState([]);
  const [kuskit, setKuskit] = useState([]);
  const [ajoneuvot, setAjoneuvot] = useState([]);

  const [paivaLokaatiot, setPaivaLokaatiot] = useState([]);
  const [paivaHenkilot, setPaivaHenkilot] = useState([]);
  const [paivaKuskit, setPaivaKuskit] = useState([]);

  const [uusiPaiva, setUusiPaiva] = useState(null); // null = lomake kiinni
  const [uusiLokaatio, setUusiLokaatio] = useState(null);
  const [virhe, setVirhe] = useState(null);

  // Viimeksi palvelimelta saatu tila per rivi, jotta blur voi verrata
  // muuttuiko arvo oikeasti eikä tallenna turhaan (sama kuvio kuin Rekisterissä).
  const tallennettuPaivaRef = useRef(null);
  const tallennettuPLRef = useRef({});
  const tallennettuPHRef = useRef({});
  const tallennettuPKRef = useRef({});

  useEffect(() => {
    api
      .haeTuotannot()
      .then((d) => {
        setTuotannot(d);
        if (d.length) setTuotantoId(String(d[0].id));
      })
      .catch((e) => setVirhe(e.message));
  }, []);

  // Tuotannon vaihtuessa: perusdata + päivälista, päivävalinta nollataan.
  useEffect(() => {
    if (!tuotantoId) return;
    setPaivaId("");
    setPaiva(null);
    setUusiPaiva(null);
    Promise.all([
      api.haeKuvauspaivatTuotannolle(tuotantoId),
      api.haeLokaatiot(tuotantoId),
      api.haeHenkilot(tuotantoId),
      api.haeKuskit(tuotantoId),
      api.haeAjoneuvot(tuotantoId),
    ])
      .then(([ps, ls, hs, ks, as]) => {
        setPaivat(ps);
        setLokaatiot(ls);
        setHenkilot(hs);
        setKuskit(ks);
        setAjoneuvot(as);
        if (ps.length) setPaivaId(String(ps[ps.length - 1].id));
      })
      .catch((e) => setVirhe(e.message));
  }, [tuotantoId]);

  // Valittu päivä poimitaan listalta. Oma efekti, jotta kenttien tallennus
  // (joka päivittää listan) ei laukaise päivän rivien uudelleenhakua.
  useEffect(() => {
    const valittu = paivat.find((p) => String(p.id) === String(paivaId));
    if (!paivaId || !valittu) {
      setPaiva(null);
      tallennettuPaivaRef.current = null;
      return;
    }
    setPaiva(muotoilePaiva(valittu));
    tallennettuPaivaRef.current = muotoilePaiva(valittu);
  }, [paivaId, paivat]);

  // Päivän vaihtuessa: päivän omat rivit.
  useEffect(() => {
    if (!paivaId) {
      setPaivaLokaatiot([]);
      setPaivaHenkilot([]);
      setPaivaKuskit([]);
      return;
    }
    Promise.all([
      api.haePaivaLokaatiot(paivaId),
      api.haePaivaHenkilot(paivaId),
      api.haePaivaKuskit(paivaId),
    ])
      .then(([pls, phs, pks]) => {
        setPaivaLokaatiot(pls.map(muotoilePL));
        tallennettuPLRef.current = Object.fromEntries(pls.map((r) => [r.id, muotoilePL(r)]));
        setPaivaHenkilot(phs.map(muotoilePH));
        tallennettuPHRef.current = Object.fromEntries(phs.map((r) => [r.id, muotoilePH(r)]));
        setPaivaKuskit(pks.map(muotoilePK));
        tallennettuPKRef.current = Object.fromEntries(pks.map((r) => [r.id, muotoilePK(r)]));
      })
      .catch((e) => setVirhe(e.message));
  }, [paivaId]);

  // --- Kuvauspäivä ---

  const muutaPaiva = (patch) => setPaiva((p) => ({ ...p, ...patch }));

  const paivaBlur = async (kentta) => {
    if (!paiva) return;
    const tallennettu = tallennettuPaivaRef.current;
    if (tallennettu && tallennettu[kentta] === paiva[kentta]) return;
    if (!aikaOut(paiva.call_time)) {
      setVirhe("Call time on pakollinen — päivää ei tallennettu.");
      return;
    }
    if (!paiva.pvm) {
      setVirhe("Päivämäärä on pakollinen — päivää ei tallennettu.");
      return;
    }
    try {
      const p = muotoilePaiva(await api.paivitaKuvauspaiva(paiva.id, paivaPayload(paiva)));
      setPaiva(p);
      tallennettuPaivaRef.current = p;
      setPaivat((ps) => ps.map((x) => (x.id === p.id ? p : x)));
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const luoPaiva = async () => {
    if (!uusiPaiva.pvm || !aikaOut(uusiPaiva.call_time)) {
      setVirhe("Uudella kuvauspäivällä pitää olla päivämäärä ja call time.");
      return;
    }
    if (paivat.some((p) => p.pvm === uusiPaiva.pvm)) {
      setVirhe(`Tuotannossa on jo kuvauspäivä ${uusiPaiva.pvm}. Valitse se listalta tai vaihda päivämäärä.`);
      return;
    }
    try {
      const luotu = await api.luoKuvauspaiva({
        ...paivaPayload({ ...uusiPaiva, tuotanto_id: Number(tuotantoId) }),
      });
      setPaivat((ps) => [...ps, luotu]);
      setPaivaId(String(luotu.id));
      setUusiPaiva(null);
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  // --- Lokaatiot ---

  const muutaPL = (id, patch) =>
    setPaivaLokaatiot((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const tallennaPL = async (rivi, patch = {}) => {
    const uusi = { ...rivi, ...patch };
    try {
      const p = muotoilePL(await api.paivitaPaivaLokaatio(uusi.id, plPayload(uusi)));
      setPaivaLokaatiot((rs) => rs.map((x) => (x.id === p.id ? p : x)));
      tallennettuPLRef.current[p.id] = p;
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const plBlur = (rivi, kentta) => {
    const tallennettu = tallennettuPLRef.current[rivi.id];
    if (tallennettu && String(tallennettu[kentta]) === String(rivi[kentta])) return;
    tallennaPL(rivi);
  };

  const lisaaPaivaLokaatio = async () => {
    const kaytetyt = new Set(paivaLokaatiot.map((r) => r.lokaatio_id));
    const vapaa = lokaatiot.find((l) => !kaytetyt.has(l.id));
    if (!vapaa) {
      setVirhe("Kaikki tuotannon lokaatiot ovat jo päivässä — luo uusi lokaatio alta.");
      return;
    }
    const jarjestys = paivaLokaatiot.reduce((m, r) => Math.max(m, Number(r.jarjestys) || 0), 0) + 1;
    try {
      const luotu = muotoilePL(
        await api.luoPaivaLokaatio({
          paiva_id: Number(paivaId),
          lokaatio_id: vapaa.id,
          jarjestys,
          siirtyma_klo: null,
        })
      );
      setPaivaLokaatiot((rs) => [...rs, luotu]);
      tallennettuPLRef.current[luotu.id] = luotu;
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const poistaPL = async (rivi) => {
    try {
      await api.poistaPaivaLokaatio(rivi.id);
      setPaivaLokaatiot((rs) => rs.filter((x) => x.id !== rivi.id));
      delete tallennettuPLRef.current[rivi.id];
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const luoLokaatioJaLisaa = async () => {
    if (!uusiLokaatio.nimi.trim()) {
      setVirhe("Lokaatiolla pitää olla nimi.");
      return;
    }
    try {
      const l = await api.luoLokaatio({
        tuotanto_id: Number(tuotantoId),
        nimi: uusiLokaatio.nimi.trim(),
        osoite: uusiLokaatio.osoite.trim() || null,
        // Ehdotuksesta valittu osoite tuo koordinaatit mukanaan; käsin
        // kirjoitettu geokoodataan backendissä.
        ...(uusiLokaatio.lat != null ? { lat: uusiLokaatio.lat, lon: uusiLokaatio.lon } : {}),
      });
      setLokaatiot((ls) => [...ls, l]);
      const jarjestys =
        paivaLokaatiot.reduce((m, r) => Math.max(m, Number(r.jarjestys) || 0), 0) + 1;
      const luotu = muotoilePL(
        await api.luoPaivaLokaatio({
          paiva_id: Number(paivaId),
          lokaatio_id: l.id,
          jarjestys,
          siirtyma_klo: null,
        })
      );
      setPaivaLokaatiot((rs) => [...rs, luotu]);
      tallennettuPLRef.current[luotu.id] = luotu;
      setUusiLokaatio(null);
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  // --- Osallistujat ---

  const phRivi = (henkiloId) => paivaHenkilot.find((r) => r.henkilo_id === henkiloId);

  const muutaPH = (id, patch) =>
    setPaivaHenkilot((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const tallennaPH = async (rivi, patch = {}) => {
    const uusi = { ...rivi, ...patch };
    try {
      const p = muotoilePH(await api.paivitaPaivaHenkilo(uusi.id, phPayload(uusi)));
      setPaivaHenkilot((rs) => rs.map((x) => (x.id === p.id ? p : x)));
      tallennettuPHRef.current[p.id] = p;
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const phBlur = (rivi, kentta) => {
    const tallennettu = tallennettuPHRef.current[rivi.id];
    if (tallennettu && String(tallennettu[kentta]) === String(rivi[kentta])) return;
    tallennaPH(rivi);
  };

  const vaihdaMukana = async (henkilo, mukana) => {
    const rivi = phRivi(henkilo.id);
    if (mukana && !rivi) {
      try {
        // Oletukset tulevat rekisteristä: henkilön oma auto -lippu pätee
        // oletuksena myös päiväkohtaisesti, koordi voi silti yliajaa sen.
        const luotu = muotoilePH(
          await api.luoPaivaHenkilo({
            paiva_id: Number(paivaId),
            henkilo_id: henkilo.id,
            oma_call: null,
            oma_auto: henkilo.oletus_oma_auto,
            ei_paluuta: false,
            siirtyy: true,
            siirtyma_klo: null,
          })
        );
        setPaivaHenkilot((rs) => [...rs, luotu]);
        tallennettuPHRef.current[luotu.id] = luotu;
        setVirhe(null);
      } catch (e) {
        setVirhe(e.message);
      }
    } else if (!mukana && rivi) {
      try {
        await api.poistaPaivaHenkilo(rivi.id);
        setPaivaHenkilot((rs) => rs.filter((x) => x.id !== rivi.id));
        delete tallennettuPHRef.current[rivi.id];
      } catch (e) {
        setVirhe(e.message);
      }
    }
  };

  // --- Kuskit ---

  const pkRivi = (kuskiId) => paivaKuskit.find((r) => r.kuski_id === kuskiId);

  const muutaPK = (id, patch) =>
    setPaivaKuskit((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  const tallennaPK = async (rivi, patch = {}) => {
    const uusi = { ...rivi, ...patch };
    try {
      const p = muotoilePK(await api.paivitaPaivaKuski(uusi.id, pkPayload(uusi)));
      setPaivaKuskit((rs) => rs.map((x) => (x.id === p.id ? p : x)));
      tallennettuPKRef.current[p.id] = p;
      setVirhe(null);
    } catch (e) {
      setVirhe(e.message);
    }
  };

  const pkBlur = (rivi, kentta) => {
    const tallennettu = tallennettuPKRef.current[rivi.id];
    if (tallennettu && String(tallennettu[kentta]) === String(rivi[kentta])) return;
    tallennaPK(rivi);
  };

  const vaihdaKuskiMukana = async (kuski, mukana) => {
    const rivi = pkRivi(kuski.id);
    if (mukana && !rivi) {
      try {
        const luotu = muotoilePK(
          await api.luoPaivaKuski({
            paiva_id: Number(paivaId),
            kuski_id: kuski.id,
            ajoneuvo_id: null,
            tarjolla: true,
            vuoro_aikaisintaan: null,
            vuoro_viimeistaan: null,
            toteutunut_alku: null,
            toteutunut_loppu: null,
          })
        );
        setPaivaKuskit((rs) => [...rs, luotu]);
        tallennettuPKRef.current[luotu.id] = luotu;
        setVirhe(null);
      } catch (e) {
        setVirhe(e.message);
      }
    } else if (!mukana && rivi) {
      try {
        await api.poistaPaivaKuski(rivi.id);
        setPaivaKuskit((rs) => rs.filter((x) => x.id !== rivi.id));
        delete tallennettuPKRef.current[rivi.id];
      } catch (e) {
        setVirhe(e.message);
      }
    }
  };

  // --- Renderöinti ---

  // Rekisteristä poistettu (passivoitu) rivi voi silti olla päivässä kiinni —
  // soft delete on tahallinen, jotta vanhat ajolistaversiot pysyvät ehjinä.
  // Näytetään ne, ettei päivä näytä hiljaa väärältä.
  const orvotPH = paivaHenkilot.filter((r) => !henkilot.some((h) => h.id === r.henkilo_id)).length;
  const orvotPK = paivaKuskit.filter((r) => !kuskit.some((k) => k.id === r.kuski_id)).length;

  const jarjestetytPL = [...paivaLokaatiot].sort(
    (a, b) => (Number(a.jarjestys) || 0) - (Number(b.jarjestys) || 0)
  );

  const osallistujaRivi = (h) => {
    const rivi = phRivi(h.id);
    const mukana = !!rivi;
    return (
      <div key={h.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
        <span style={{ width: 150 }}>
          <Ruksi checked={mukana} onChange={(v) => vaihdaMukana(h, v)} label={henkiloNimi(h)} />
        </span>
        {h.titteli && (
          <span style={{ fontFamily: "'Archivo',sans-serif", fontSize: 12, color: C.olive }}>
            {h.titteli}
          </span>
        )}
        {mukana && (
          <>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={pikkuLabel}>oma call</span>
              <Kentta
                type="time"
                value={rivi.oma_call}
                onChange={(v) => muutaPH(rivi.id, { oma_call: v })}
                onBlur={() => phBlur(rivi, "oma_call")}
                w={110}
              />
            </span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
              <span style={pikkuLabel}>siirtyy klo</span>
              <Kentta
                type="time"
                value={rivi.siirtyma_klo}
                onChange={(v) => muutaPH(rivi.id, { siirtyma_klo: v })}
                onBlur={() => phBlur(rivi, "siirtyma_klo")}
                w={110}
              />
            </span>
            <span style={{ marginLeft: "auto", display: "flex", gap: 10, flexWrap: "wrap" }}>
              <Ruksi
                checked={rivi.oma_auto}
                onChange={(v) => tallennaPH(rivi, { oma_auto: v })}
                label="oma auto"
              />
              <Ruksi
                checked={rivi.ei_paluuta}
                onChange={(v) => tallennaPH(rivi, { ei_paluuta: v })}
                label="ei paluuta"
              />
              <Ruksi
                checked={rivi.siirtyy}
                onChange={(v) => tallennaPH(rivi, { siirtyy: v })}
                label="siirtymässä"
              />
            </span>
          </>
        )}
      </div>
    );
  };

  return (
    <div>
      <Kortti otsikko="Tuotanto ja kuvauspäivä" nro="◆">
        {!tuotannot.length && (
          <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
            Ei tuotantoja. Luo yksi esim. <code>python -m app.seed</code> backendissä.
          </p>
        )}
        {!!tuotannot.length && (
          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div>
              <div style={pikkuLabel}>Tuotanto</div>
              <select
                value={tuotantoId}
                onChange={(e) => setTuotantoId(e.target.value)}
                style={valintaTyyli}
              >
                {tuotannot.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.nimi}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <div style={pikkuLabel}>Kuvauspäivä</div>
              <select
                value={paivaId}
                onChange={(e) => setPaivaId(e.target.value)}
                style={valintaTyyli}
              >
                <option value="">— valitse —</option>
                {paivat.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.pvm} {p.paiva_nro ? `· ${p.paiva_nro}` : ""}
                  </option>
                ))}
              </select>
            </div>
            {!uusiPaiva && (
              <Nappi
                variant="ghost"
                onClick={() =>
                  setUusiPaiva({
                    pvm: tanaan(),
                    paiva_nro: "",
                    call_time: "08:00",
                    lounas: "",
                    wrap_arvio: "",
                  })
                }
              >
                + Uusi kuvauspäivä
              </Nappi>
            )}
          </div>
        )}

        {uusiPaiva && (
          <div
            style={{
              marginTop: 14,
              paddingTop: 14,
              borderTop: `1px solid ${C.ink}`,
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              alignItems: "flex-end",
            }}
          >
            <div>
              <div style={pikkuLabel}>Päivämäärä</div>
              <Kentta
                type="date"
                value={uusiPaiva.pvm}
                onChange={(v) => setUusiPaiva((u) => ({ ...u, pvm: v }))}
                w={140}
              />
            </div>
            <div>
              <div style={pikkuLabel}>Päivä nro</div>
              <Kentta
                value={uusiPaiva.paiva_nro}
                onChange={(v) => setUusiPaiva((u) => ({ ...u, paiva_nro: v }))}
                w={70}
                ph="22/49"
              />
            </div>
            <div>
              <div style={pikkuLabel}>Call</div>
              <Kentta
                type="time"
                value={uusiPaiva.call_time}
                onChange={(v) => setUusiPaiva((u) => ({ ...u, call_time: v }))}
                w={110}
              />
            </div>
            <div>
              <div style={pikkuLabel}>Lounas</div>
              <Kentta
                type="time"
                value={uusiPaiva.lounas}
                onChange={(v) => setUusiPaiva((u) => ({ ...u, lounas: v }))}
                w={110}
              />
            </div>
            <div>
              <div style={pikkuLabel}>Wrap</div>
              <Kentta
                type="time"
                value={uusiPaiva.wrap_arvio}
                onChange={(v) => setUusiPaiva((u) => ({ ...u, wrap_arvio: v }))}
                w={110}
              />
            </div>
            <Nappi onClick={luoPaiva}>Luo päivä</Nappi>
            <Nappi variant="ghost" onClick={() => setUusiPaiva(null)}>
              Peruuta
            </Nappi>
          </div>
        )}

        {paiva && (
          <div
            style={{
              marginTop: 14,
              paddingTop: 14,
              borderTop: `1px solid ${C.ink}`,
              display: "flex",
              gap: 10,
              flexWrap: "wrap",
              alignItems: "flex-end",
            }}
          >
            <div>
              <div style={pikkuLabel}>Päivämäärä</div>
              <Kentta
                type="date"
                value={paiva.pvm}
                onChange={(v) => muutaPaiva({ pvm: v })}
                onBlur={() => paivaBlur("pvm")}
                w={140}
              />
            </div>
            <div>
              <div style={pikkuLabel}>Päivä nro</div>
              <Kentta
                value={paiva.paiva_nro || ""}
                onChange={(v) => muutaPaiva({ paiva_nro: v })}
                onBlur={() => paivaBlur("paiva_nro")}
                w={70}
                ph="22/49"
              />
            </div>
            <div>
              <div style={pikkuLabel}>Call</div>
              <Kentta
                type="time"
                value={paiva.call_time}
                onChange={(v) => muutaPaiva({ call_time: v })}
                onBlur={() => paivaBlur("call_time")}
                w={110}
              />
            </div>
            <div>
              <div style={pikkuLabel}>Lounas</div>
              <Kentta
                type="time"
                value={paiva.lounas}
                onChange={(v) => muutaPaiva({ lounas: v })}
                onBlur={() => paivaBlur("lounas")}
                w={110}
              />
            </div>
            <div>
              <div style={pikkuLabel}>Wrap</div>
              <Kentta
                type="time"
                value={paiva.wrap_arvio}
                onChange={(v) => muutaPaiva({ wrap_arvio: v })}
                onBlur={() => paivaBlur("wrap_arvio")}
                w={110}
              />
            </div>
            {!paiva.wrap_arvio && <Badge color={C.rust}>wrap puuttuu</Badge>}
          </div>
        )}
        {paiva && !paiva.wrap_arvio && (
          <p style={vihje}>
            Wrap-arvio tarvitaan paluukyytien generointiin — ilman sitä tehtävägenerointi
            kieltäytyy, jos joku tarvitsee paluun.
          </p>
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

      {!paivaId && !!tuotannot.length && (
        <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
          Valitse tai luo kuvauspäivä, niin pääset täyttämään lokaatiot, osallistujat ja kuskit.
        </p>
      )}

      {!!paivaId && (
        <>
          <Kortti otsikko="Lokaatiot" nro="A" lisa={`${jarjestetytPL.length} kpl`}>
            {jarjestetytPL.map((r) => (
              <div key={r.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={pikkuLabel}>nro</span>
                  <Kentta
                    type="number"
                    value={String(r.jarjestys)}
                    onChange={(v) => muutaPL(r.id, { jarjestys: v })}
                    onBlur={() => plBlur(r, "jarjestys")}
                    w={48}
                  />
                </span>
                <select
                  value={r.lokaatio_id}
                  onChange={(e) => tallennaPL(r, { lokaatio_id: Number(e.target.value) })}
                  style={valintaTyyli}
                >
                  {lokaatiot.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.nimi}
                    </option>
                  ))}
                  {!lokaatiot.some((l) => l.id === r.lokaatio_id) && (
                    <option value={r.lokaatio_id}>(rekisteristä poistettu lokaatio)</option>
                  )}
                </select>
                <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11, color: C.olive }}>
                  {lokaatiot.find((l) => l.id === r.lokaatio_id)?.osoite || "ei osoitetta"}
                </span>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  <span style={pikkuLabel}>siirtymä tänne klo</span>
                  <Kentta
                    type="time"
                    value={r.siirtyma_klo}
                    onChange={(v) => muutaPL(r.id, { siirtyma_klo: v })}
                    onBlur={() => plBlur(r, "siirtyma_klo")}
                    w={110}
                  />
                </span>
                <button
                  onClick={() => poistaPL(r)}
                  style={{
                    marginLeft: "auto",
                    border: "none",
                    background: "none",
                    cursor: "pointer",
                    color: C.rust,
                    fontWeight: 900,
                    fontSize: 16,
                  }}
                >
                  ×
                </button>
              </div>
            ))}

            <div style={{ marginTop: 12, display: "flex", gap: 10, flexWrap: "wrap" }}>
              <Nappi variant="ghost" onClick={lisaaPaivaLokaatio}>
                + Lisää lokaatio päivään
              </Nappi>
              {!uusiLokaatio && (
                <Nappi variant="ghost" onClick={() => setUusiLokaatio({ nimi: "", osoite: "", lat: null, lon: null })}>
                  + Luo uusi lokaatio
                </Nappi>
              )}
            </div>

            {uusiLokaatio && (
              <div
                style={{
                  marginTop: 12,
                  display: "flex",
                  gap: 10,
                  flexWrap: "wrap",
                  alignItems: "flex-end",
                }}
              >
                <div>
                  <div style={pikkuLabel}>Nimi</div>
                  <Kentta
                    value={uusiLokaatio.nimi}
                    onChange={(v) => setUusiLokaatio((u) => ({ ...u, nimi: v }))}
                    w={160}
                    ph="LOC 1, Hamarin talo"
                  />
                </div>
                <div>
                  <div style={pikkuLabel}>Osoite</div>
                  <OsoiteKentta
                    value={uusiLokaatio.osoite}
                    onChange={(v) => setUusiLokaatio((u) => ({ ...u, osoite: v, lat: null, lon: null }))}
                    onValitse={(e) => setUusiLokaatio((u) => ({ ...u, osoite: e.nimi, lat: e.lat, lon: e.lon }))}
                    w={260}
                    ph="Ala kirjoittaa osoitetta…"
                  />
                </div>
                <Nappi onClick={luoLokaatioJaLisaa}>Luo ja lisää</Nappi>
                <Nappi variant="ghost" onClick={() => setUusiLokaatio(null)}>
                  Peruuta
                </Nappi>
              </div>
            )}

            <p style={vihje}>
              Järjestysnumero ratkaisee mistä mihin siirrytään: aamun noudot vievät
              ensimmäiseen lokaatioon, ja "siirtymä tänne klo" on se hetki jolloin ryhmä
              siirtyy tähän lokaatioon edellisestä.
            </p>
          </Kortti>

          <Kortti
            otsikko="Ketkä ovat mukana"
            nro="B"
            lisa={`${paivaHenkilot.length}/${henkilot.length}`}
          >
            {!henkilot.length && (
              <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
                Tuotannossa ei ole henkilöitä. Lisää heidät Rekisteri-välilehdellä.
              </p>
            )}
            {henkilot.some((h) => h.tyyppi === "cast") && (
              <div style={pikkuLabel}>Näyttelijät</div>
            )}
            {henkilot.filter((h) => h.tyyppi === "cast").map(osallistujaRivi)}
            {henkilot.some((h) => h.tyyppi === "crew") && (
              <div style={{ ...pikkuLabel, marginTop: 14 }}>Työryhmä</div>
            )}
            {henkilot.filter((h) => h.tyyppi === "crew").map(osallistujaRivi)}
            {orvotPH > 0 && (
              <p style={{ ...vihje, color: C.rust }}>
                Päivässä on {orvotPH} henkilöä, jotka on poistettu rekisteristä. He ovat
                mukana tehtävissä ja vanhoissa versioissa, mutta eivät näy tässä listassa.
              </p>
            )}
            <p style={vihje}>
              Tyhjä "oma call" tarkoittaa päivän yleistä call timea. "Oma auto" tulee
              oletuksena rekisteristä — sen voi yliajaa päiväkohtaisesti. "Siirtyy klo"
              ohittaa lokaation yleisen siirtymäajan, jos tämä henkilö siirtyy muista
              poikkeavaan aikaan.
            </p>
          </Kortti>

          <Kortti
            otsikko="Kuskit"
            nro="C"
            lisa={`${paivaKuskit.filter((r) => r.tarjolla).length} tarjolla`}
          >
            {!kuskit.length && (
              <p style={{ fontFamily: "'Archivo',sans-serif", fontSize: 13, color: C.olive }}>
                Tuotannossa ei ole kuskeja. Lisää heidät Rekisteri-välilehdellä.
              </p>
            )}
            {kuskit.map((k) => {
              const rivi = pkRivi(k.id);
              const mukana = !!rivi;
              return (
                <div key={k.id} style={{ ...riviTyyli, flexWrap: "wrap" }}>
                  <span style={{ width: 150 }}>
                    <Ruksi
                      checked={mukana}
                      onChange={(v) => vaihdaKuskiMukana(k, v)}
                      label={k.nimi || "(nimetön)"}
                    />
                  </span>
                  {mukana && (
                    <>
                      <select
                        value={rivi.ajoneuvo_id ?? ""}
                        onChange={(e) =>
                          tallennaPK(rivi, {
                            ajoneuvo_id: e.target.value === "" ? null : Number(e.target.value),
                          })
                        }
                        style={valintaTyyli}
                      >
                        <option value="">— ei autoa —</option>
                        {ajoneuvot.map((a) => (
                          <option key={a.id} value={a.id}>
                            {a.nimi} ({a.mukavuuspaikat} paikkaa)
                          </option>
                        ))}
                      </select>
                      {rivi.ajoneuvo_id == null && <Badge color={C.rust}>auto puuttuu</Badge>}
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <span style={pikkuLabel}>vuoro</span>
                        <Kentta
                          type="time"
                          value={rivi.vuoro_aikaisintaan}
                          onChange={(v) => muutaPK(rivi.id, { vuoro_aikaisintaan: v })}
                          onBlur={() => pkBlur(rivi, "vuoro_aikaisintaan")}
                          w={110}
                        />
                        <span style={{ fontFamily: "'IBM Plex Mono',monospace", fontSize: 11 }}>–</span>
                        <Kentta
                          type="time"
                          value={rivi.vuoro_viimeistaan}
                          onChange={(v) => muutaPK(rivi.id, { vuoro_viimeistaan: v })}
                          onBlur={() => pkBlur(rivi, "vuoro_viimeistaan")}
                          w={110}
                        />
                      </span>
                      <span style={{ marginLeft: "auto" }}>
                        <Ruksi
                          checked={rivi.tarjolla}
                          onChange={(v) => tallennaPK(rivi, { tarjolla: v })}
                          label="tarjolla"
                        />
                      </span>
                    </>
                  )}
                </div>
              );
            })}
            {orvotPK > 0 && (
              <p style={{ ...vihje, color: C.rust }}>
                Päivässä on {orvotPK} kuskia, jotka on poistettu rekisteristä. He eivät näy
                tässä listassa, mutta ovat edelleen päivän datassa.
              </p>
            )}
            <p style={vihje}>
              Optimointi käyttää vain tarjolla olevia kuskeja, ja jokainen tarvitsee auton.
              Vuororajat ovat valinnaisia — esimerkiksi kuvaajan vuokra-auto voi olla
              käytettävissä vasta wrapin jälkeen.
            </p>
          </Kortti>
        </>
      )}
    </div>
  );
}

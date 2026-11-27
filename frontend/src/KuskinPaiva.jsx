/* Kuskin päivänäkymä puhelimelle (ROADMAP N2).

   KUSKI-rooli näkee tämän näkymän Optimointi-välilehden sijaan: oma päivä
   julkaistusta ajolistasta, keikat aikajärjestyksessä ryhmiteltyinä
   kyydeiksi, nouto- ja jättöosoitteet karttalinkkeinä ja kyytiläisten
   puhelinnumerot soittonappeina.

   Kaikki tieto tulee olemassa olevista endpointeista. Backend rajaa jo
   KUSKI-roolille vain julkaistut versiot ja omat keikat (N1), joten tämä
   näkymä ei voi näyttää muiden kuskien keikkoja eikä kustannuksia, vaikka
   päivän tehtävä- ja henkilölistat haetaan kokonaisina yhteystietoja varten.

   Karttalinkki on tavallinen linkki Google Mapsin reittihakuun
   (https://www.google.com/maps/dir/?api=1&destination=...). Sovellus ei
   kutsu karttapalvelua itse; puhelin avaa linkin karttasovelluksessa vasta,
   kun kuski napauttaa sitä.

   Kuittaukset (ROADMAP N3): jokaisella noudolla on iso nappi, joka vie
   keikan tilan eteenpäin: "Kyydissä" noudettaessa ja "Perillä" jätettäessä.
   Backend sallii kuskille vain oman keikan ja vain eteenpäin; virheen
   sattuessa (esim. koordi on julkaissut uuden version) viesti näkyy noudon
   alla ja "↻ Päivitä" hakee ajantasaisen listan. */

import { useEffect, useState } from "react";
import {
  asetaKeikanTila,
  haeAjoneuvot,
  haeHenkilot,
  haeKeikat,
  haeKuvauspaivat,
  haePaivaHenkilot,
  haePaivaKuskit,
  haeTehtavat,
  haeVersiot,
} from "./api.js";
import { C, Nappi, t } from "./ui.jsx";
import Versiodiff from "./Versiodiff.jsx";

const VIIKONPAIVAT = ["su", "ma", "ti", "ke", "to", "pe", "la"];
const klo = (s) => (s ? s.slice(0, 5) : "");

function muotoilePvm(iso) {
  const [v, k, p] = iso.split("-").map(Number);
  return `${VIIKONPAIVAT[new Date(v, k - 1, p).getDay()]} ${p}.${k}.`;
}

function tanaanIso() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Oletuspäivä: tämä päivä, sen puuttuessa seuraava tuleva, ja jos kaikki
// ovat menneitä, viimeisin.
function valitseOletusPaiva(paivat, tanaan = tanaanIso()) {
  if (!paivat.length) return null;
  const jarjestetty = [...paivat].sort((a, b) => a.pvm.localeCompare(b.pvm));
  return jarjestetty.find((p) => p.pvm >= tanaan) ?? jarjestetty[jarjestetty.length - 1];
}

// Karttalinkki: koordinaatit, jos tehtävässä on ne, muuten osoite tekstinä.
function karttaLinkki(osoite, lat, lon) {
  const kohde = lat != null && lon != null ? `${lat},${lon}` : osoite;
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(kohde)}`;
}

// Aikaleimat ovat kannassa UTC:nä ilman aikavyöhykettä -> paikallinen kello.
const kellonaika = (iso) =>
  iso ? new Date(`${iso}Z`).toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit" }) : "";

// tel:-linkistä pois välilyönnit ja väliviivat ("040 123 4567" -> "0401234567").
const puhelinLinkki = (numero) => `tel:${numero.replace(/[^\d+]/g, "")}`;

/* Keikat kyydeiksi: kuskin keikat, joiden aikavälit menevät päällekkäin,
   ovat samassa autossa yhtä aikaa (kimppakyyti). Keikat järjestetään
   noudon mukaan, ja uusi kyyti alkaa, kun seuraava nouto on vasta edellisten
   jättöjen jälkeen. */
function ryhmitteleKyydeiksi(keikat) {
  const jarjestetyt = [...keikat].sort(
    (a, b) => t(klo(a.nouto_klo)) - t(klo(b.nouto_klo)) || a.jarjestys - b.jarjestys
  );
  const kyydit = [];
  let nykyinen = null;
  for (const k of jarjestetyt) {
    const nouto = t(klo(k.nouto_klo));
    const jatto = t(klo(k.jatto_klo));
    if (nykyinen && nouto < nykyinen.loppu) {
      nykyinen.keikat.push(k);
      nykyinen.loppu = Math.max(nykyinen.loppu, jatto);
    } else {
      nykyinen = { alku: nouto, loppu: jatto, keikat: [k] };
      kyydit.push(nykyinen);
    }
  }
  return kyydit;
}

async function haeKuskinPaiva(paiva) {
  // KUSKI saa vain julkaistut versiot (N1). Uusin julkaistu on voimassa.
  const versiot = await haeVersiot(paiva.id);
  if (!versiot.length) return { versio: null, keikat: [] };
  const versio = versiot.reduce((a, b) => (b.versio_nro > a.versio_nro ? b : a));

  const [keikat, tehtavat, henkilot, paivaHenkilot, paivaKuskit, ajoneuvot] = await Promise.all([
    haeKeikat(versio.id), // vain omat keikat (N1)
    // Passiiviset mukaan: julkaistussa versiossa voi olla keikka tehtävälle,
    // joka on poistettu (soft delete) julkaisun jälkeen.
    haeTehtavat(paiva.id, { sisallaPassiiviset: true }),
    haeHenkilot(paiva.tuotanto_id),
    haePaivaHenkilot(paiva.id),
    haePaivaKuskit(paiva.id),
    haeAjoneuvot(paiva.tuotanto_id),
  ]);

  const tehtavaById = new Map(tehtavat.map((x) => [x.id, x]));
  const henkiloById = new Map(henkilot.map((h) => [h.id, h]));
  const paivaHuomiot = new Map(paivaHenkilot.map((ph) => [ph.henkilo_id, ph.huomiot]));

  const rikastetut = keikat.map((k) => {
    const teht = tehtavaById.get(k.tehtava_id);
    const henkilo = teht?.henkilo_id ? henkiloById.get(teht.henkilo_id) : null;
    return {
      ...k,
      nimi: teht?.nimi ?? `Tehtävä ${k.tehtava_id}`,
      henkiloita: teht?.henkiloita ?? 1,
      mista: teht?.mista_osoite ?? "",
      mista_linkki: teht ? karttaLinkki(teht.mista_osoite, teht.mista_lat, teht.mista_lon) : null,
      mihin: teht?.mihin_osoite ?? "",
      mihin_linkki: teht ? karttaLinkki(teht.mihin_osoite, teht.mihin_lat, teht.mihin_lon) : null,
      henkilo: henkilo
        ? { nimi: henkilo.nimi, kuvaus: henkilo.roolinimi || henkilo.titteli || null, puhelin: henkilo.puhelin }
        : null,
      huomiot: [teht?.huomiot, henkilo ? paivaHuomiot.get(henkilo.id) : null].filter(Boolean),
    };
  });

  // Oma auto: keikkojen päiväkuski on aina kuski itse.
  const omaPaivaKuskiId = keikat[0]?.paiva_kuski_id;
  const pk = paivaKuskit.find((x) => x.id === omaPaivaKuskiId);
  const auto = pk ? ajoneuvot.find((a) => a.id === pk.ajoneuvo_id) : null;

  return {
    versio,
    keikat: rikastetut,
    auto: auto ? [auto.nimi, auto.rekisteri].filter(Boolean).join(" ") : null,
  };
}

// --- Tyylit: iso teksti ja isot kosketusalueet puhelimelle ---

const leipa = { fontFamily: "'Archivo',sans-serif", fontSize: 17, color: C.inkSolid, lineHeight: 1.35 };
const kello = { fontFamily: "'IBM Plex Mono',monospace", fontWeight: 600, fontSize: 20, color: C.inkSolid };
const pieni = { fontFamily: "'Archivo',sans-serif", fontSize: 14, color: C.olive, fontWeight: 600 };

const isoNappi = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  minHeight: 52,
  padding: "10px 16px",
  borderRadius: 14,
  border: `2px solid ${C.line}`,
  boxShadow: `3px 3px 0 ${C.line}`,
  fontFamily: "'Archivo',sans-serif",
  fontWeight: 700,
  fontSize: 17,
  textDecoration: "none",
  color: C.inkSolid,
  background: C.card,
  boxSizing: "border-box",
  width: "100%",
};

function KarttaNappi({ osoite, linkki }) {
  if (!osoite) return null;
  return (
    <a href={linkki} target="_blank" rel="noopener noreferrer" style={isoNappi} aria-label={`Avaa kartalla: ${osoite}`}>
      <span aria-hidden="true">📍</span>
      <span style={{ flex: 1, minWidth: 0, overflowWrap: "anywhere" }}>{osoite}</span>
    </a>
  );
}

function SoittoNappi({ nimi, puhelin }) {
  if (!puhelin) return null;
  return (
    <a
      href={puhelinLinkki(puhelin)}
      style={{ ...isoNappi, background: C.teal, color: C.card }}
      aria-label={`Soita: ${nimi}, ${puhelin}`}
    >
      <span aria-hidden="true">📞</span>
      <span>Soita {puhelin}</span>
    </a>
  );
}

// Seuraava kuittaus tilasta: odottaa -> kyydissä -> perillä.
const SEURAAVA = {
  odottaa: { tila: "kyydissa", teksti: "Kyydissä", kuvaus: "Merkitse noudetuksi" },
  kyydissa: { tila: "perilla", teksti: "Perillä", kuvaus: "Merkitse perille viedyksi" },
};

function TilaNappi({ k, kyytilainen, onMuuttui }) {
  const [lahettaa, setLahettaa] = useState(false);
  const [virhe, setVirhe] = useState(null);
  const seuraava = SEURAAVA[k.tila];

  async function kuittaa() {
    setLahettaa(true);
    setVirhe(null);
    try {
      onMuuttui(await asetaKeikanTila(k.id, seuraava.tila));
    } catch (e) {
      setVirhe(e.message);
    } finally {
      setLahettaa(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 6 }}>
      {k.tila !== "odottaa" && (
        <div style={{ ...pieni, color: C.teal }}>
          {k.kyydissa_klo && `✓ Kyydissä ${kellonaika(k.kyydissa_klo)}`}
          {k.kyydissa_klo && k.perilla_klo && " · "}
          {k.perilla_klo && `✓ Perillä ${kellonaika(k.perilla_klo)}`}
        </div>
      )}
      {seuraava && (
        <button
          type="button"
          onClick={kuittaa}
          disabled={lahettaa}
          aria-label={`${seuraava.kuvaus}: ${kyytilainen}`}
          style={{
            ...isoNappi,
            justifyContent: "center",
            cursor: lahettaa ? "wait" : "pointer",
            opacity: lahettaa ? 0.6 : 1,
            background: k.tila === "odottaa" ? C.ochre : C.teal,
            color: k.tila === "odottaa" ? C.inkSolid : C.card,
          }}
        >
          <span aria-hidden="true">✓</span>
          <span>{lahettaa ? "Tallennetaan…" : seuraava.teksti}</span>
        </button>
      )}
      {virhe && (
        <div role="alert" style={{ ...pieni, color: C.rust }}>
          ⚠ Kuittaus epäonnistui: {virhe}
        </div>
      )}
    </div>
  );
}

function Nouto({ k, onKeikkaMuuttui }) {
  const kyytilainen = k.henkilo?.nimi ?? k.nimi;
  return (
    <div style={{ padding: "14px 0", borderBottom: `1px solid ${C.ink}` }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
        <span style={kello}>{klo(k.nouto_klo)}</span>
        <span style={{ ...leipa, fontWeight: 700 }}>{kyytilainen}</span>
        {k.henkilo?.kuvaus && <span style={pieni}>{k.henkilo.kuvaus}</span>}
        {k.henkiloita > 1 && <span style={pieni}>{k.henkiloita} hlö</span>}
        {k.henkiloita === 0 && <span style={pieni}>tavara</span>}
        {k.kuitattu && k.tila !== "perilla" && <span style={{ ...pieni, color: C.teal }}>✓ kuitattu</span>}
      </div>
      {/* Tehtävän nimi vain, jos se kertoo jotain muuta kuin "Nouto: <nimi>" */}
      {k.henkilo && !k.nimi.includes(kyytilainen) && <div style={{ ...pieni, marginBottom: 8 }}>{k.nimi}</div>}
      <div style={{ display: "grid", gap: 10 }}>
        <KarttaNappi osoite={k.mista} linkki={k.mista_linkki} />
        {k.henkilo && <SoittoNappi nimi={kyytilainen} puhelin={k.henkilo.puhelin} />}
        <TilaNappi k={k} kyytilainen={kyytilainen} onMuuttui={onKeikkaMuuttui} />
      </div>
      {k.huomiot.map((h, i) => (
        <div
          key={i}
          style={{
            ...leipa,
            fontSize: 16,
            marginTop: 10,
            padding: "8px 12px",
            background: "#F7E7BE",
            border: `2px solid ${C.ochre}`,
            borderRadius: 10,
          }}
        >
          ⚠ {h}
        </div>
      ))}
    </div>
  );
}

// Jätöt: samaan osoitteeseen samaan aikaan jätettävät yhdistetään.
function jatot(keikat) {
  const tulos = [];
  for (const k of [...keikat].sort((a, b) => t(klo(a.jatto_klo)) - t(klo(b.jatto_klo)))) {
    const sama = tulos.find((j) => j.mihin === k.mihin && j.klo === klo(k.jatto_klo));
    const nimi = k.henkilo?.nimi ?? k.nimi;
    if (sama) sama.nimet.push(nimi);
    else tulos.push({ klo: klo(k.jatto_klo), mihin: k.mihin, linkki: k.mihin_linkki, nimet: [nimi] });
  }
  return tulos;
}

function Kyyti({ kyyti, nro, onKeikkaMuuttui }) {
  const henkiloita = kyyti.keikat.reduce((s, k) => s + k.henkiloita, 0);
  return (
    <section
      style={{
        background: C.card,
        border: `2px solid ${C.line}`,
        borderRadius: 16,
        boxShadow: `4px 4px 0 ${C.line}`,
        padding: "14px 16px 16px",
        marginBottom: 20,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
        <h2 style={{ fontFamily: "'Fraunces',serif", fontWeight: 900, fontSize: 24, margin: 0, color: C.inkSolid }}>
          Kyyti {nro}
        </h2>
        <span style={kello}>
          {klo(kyyti.keikat[0].nouto_klo)}–{jatot(kyyti.keikat).at(-1).klo}
        </span>
        {kyyti.keikat.length > 1 && <span style={pieni}>{henkiloita} kyydissä</span>}
      </div>

      <div style={{ ...pieni, marginTop: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
        {kyyti.keikat.length > 1 ? "Noudot" : "Nouto"}
      </div>
      {kyyti.keikat.map((k) => (
        <Nouto key={k.id} k={k} onKeikkaMuuttui={onKeikkaMuuttui} />
      ))}

      <div style={{ ...pieni, marginTop: 14, textTransform: "uppercase", letterSpacing: "0.06em" }}>Perillä</div>
      {jatot(kyyti.keikat).map((j, i) => (
        <div key={i} style={{ padding: "12px 0 0" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
            <span style={kello}>{j.klo}</span>
            {kyyti.keikat.length > 1 && <span style={leipa}>{j.nimet.join(", ")}</span>}
          </div>
          <KarttaNappi osoite={j.mihin} linkki={j.linkki} />
        </div>
      ))}
    </section>
  );
}

export default function KuskinPaiva() {
  const [paivat, setPaivat] = useState([]);
  const [paivatLadattu, setPaivatLadattu] = useState(false);
  const [paivatVirhe, setPaivatVirhe] = useState(null);
  const [valittuId, setValittuId] = useState("");
  // "↻ Päivitä" kasvattaa laskuria, joka käynnistää haun uudelleen.
  const [paivitys, setPaivitys] = useState(0);
  // Viimeisin hakutulos: { avain, data, virhe, aika }. Lataustila päätellään
  // vertaamalla avainta nykyiseen, jotta efektissä ei aseteta tilaa suoraan.
  const [haku, setHaku] = useState(null);

  useEffect(() => {
    haeKuvauspaivat()
      .then((p) => {
        setPaivat(p);
        const oletus = valitseOletusPaiva(p);
        if (oletus) setValittuId(String(oletus.id));
      })
      .catch((e) => setPaivatVirhe(`Kuvauspäivien haku epäonnistui: ${e.message}`))
      .finally(() => setPaivatLadattu(true));
  }, []);

  const paiva = paivat.find((p) => String(p.id) === valittuId);
  const avain = paiva ? `${paiva.id}:${paivitys}` : null;

  useEffect(() => {
    if (!paiva) return;
    let peruttu = false;
    const omaAvain = `${paiva.id}:${paivitys}`;
    haeKuskinPaiva(paiva)
      .then((d) => !peruttu && setHaku({ avain: omaAvain, paivaId: paiva.id, data: d, virhe: null, aika: new Date() }))
      .catch(
        (e) =>
          !peruttu &&
          setHaku((ed) => ({
            avain: omaAvain,
            paivaId: paiva.id,
            // Päivityksen virhe jättää edellisen listan näkyviin.
            data: ed?.paivaId === paiva.id ? ed.data : null,
            virhe: `Ajolistan haku epäonnistui: ${e.message}`,
            aika: ed?.aika ?? null,
          }))
      );
    return () => {
      peruttu = true;
    };
  }, [paiva, paivitys]);

  const lataa = !paivatLadattu || (avain !== null && haku?.avain !== avain);
  const data = haku && paiva && haku.paivaId === paiva.id ? haku.data : null;
  const virhe = paivatVirhe ?? (haku?.avain === avain ? haku.virhe : null);
  const paivitetty = data ? haku.aika : null;

  // Kuittauksen vastaus päivittää vain kyseisen keikan tilan, ei koko listaa.
  function paivitaKeikka(uusi) {
    setHaku((ed) =>
      ed?.data
        ? {
            ...ed,
            data: {
              ...ed.data,
              keikat: ed.data.keikat.map((k) =>
                k.id === uusi.id
                  ? { ...k, tila: uusi.tila, kyydissa_klo: uusi.kyydissa_klo, perilla_klo: uusi.perilla_klo, kuitattu: uusi.kuitattu }
                  : k
              ),
            },
          }
        : ed
    );
  }

  const jarjestetytPaivat = [...paivat].sort((a, b) => a.pvm.localeCompare(b.pvm));
  const kyydit = data ? ryhmitteleKyydeiksi(data.keikat) : [];

  return (
    <div style={{ maxWidth: 560, margin: "0 auto" }}>
      {!!paivat.length && (
        <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
          <label htmlFor="kuski-paiva" style={{ ...pieni, width: "100%" }}>
            Kuvauspäivä
          </label>
          <select
            id="kuski-paiva"
            value={valittuId}
            onChange={(e) => setValittuId(e.target.value)}
            style={{
              flex: 1,
              minWidth: 0,
              minHeight: 52,
              fontFamily: "'IBM Plex Mono',monospace",
              fontWeight: 600,
              fontSize: 17,
              padding: "8px 12px",
              border: `2px solid ${C.line}`,
              borderRadius: 12,
              background: C.card,
              color: C.inkSolid,
            }}
          >
            {jarjestetytPaivat.map((p) => (
              <option key={p.id} value={p.id}>
                {muotoilePvm(p.pvm)}
                {p.pvm === tanaanIso() ? " (tänään)" : ""}
                {p.paiva_nro ? ` · ${p.paiva_nro}` : ""}
              </option>
            ))}
          </select>
          <Nappi onClick={() => setPaivitys((n) => n + 1)} disabled={lataa} style={{ minHeight: 52, fontSize: 16 }}>
            ↻ Päivitä
          </Nappi>
        </div>
      )}

      {paiva && (
        <div style={{ ...leipa, marginBottom: 16 }}>
          <b>Call {klo(paiva.call_time)}</b>
          {paiva.wrap_arvio ? ` · wrap n. ${klo(paiva.wrap_arvio)}` : ""}
          {data?.auto ? ` · auto ${data.auto}` : ""}
          {paiva.huomiot && <div style={{ ...pieni, marginTop: 4 }}>{paiva.huomiot}</div>}
        </div>
      )}

      {virhe && (
        <div
          role="alert"
          style={{
            ...leipa,
            fontWeight: 600,
            color: C.rust,
            border: `2px solid ${C.rust}`,
            background: "#F7DFD2",
            borderRadius: 12,
            padding: "12px 14px",
            marginBottom: 16,
          }}
        >
          ⚠ {virhe}
        </div>
      )}

      {lataa && !data && <p style={{ ...leipa, color: C.olive, textAlign: "center", padding: 30 }}>Haetaan ajolistaa…</p>}

      {!lataa && !virhe && !paivat.length && (
        <p style={{ ...leipa, color: C.olive, textAlign: "center", padding: 30 }}>Ei kuvauspäiviä.</p>
      )}

      {data && !data.versio && (
        <p style={{ ...leipa, color: C.olive, textAlign: "center", padding: 30 }}>
          Tälle päivälle ei ole vielä julkaistua ajolistaa. Tarkista myöhemmin uudelleen.
        </p>
      )}

      {data?.versio && !data.keikat.length && (
        <p style={{ ...leipa, color: C.olive, textAlign: "center", padding: 30 }}>
          Sinulla ei ole keikkoja tänä päivänä.
        </p>
      )}

      {data?.versio && !!data.keikat.length && (
        <>
          <div style={{ ...pieni, marginBottom: 12 }}>
            {data.keikat.length} {data.keikat.length === 1 ? "keikka" : "keikkaa"} · ajolista v{data.versio.versio_nro}
            {paivitetty &&
              ` · päivitetty ${paivitetty.toLocaleTimeString("fi-FI", { hour: "2-digit", minute: "2-digit" })}`}
          </div>
          {kyydit.map((k, i) => (
            <Kyyti key={k.keikat[0].id} kyyti={k} nro={i + 1} onKeikkaMuuttui={paivitaKeikka} />
          ))}
        </>
      )}

      {data?.versio && <Versiodiff paivaId={paiva.id} nykyinenVersioId={data.versio.id} />}
    </div>
  );
}

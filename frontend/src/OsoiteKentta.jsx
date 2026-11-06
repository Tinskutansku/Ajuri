import { useEffect, useRef, useState } from "react";
import * as api from "./api.js";
import { C } from "./ui.jsx";

// Osoitekenttä, joka ehdottaa osoitteita kirjoittaessa (GET /osoitteet/ehdota,
// Photon). Valinta antaa onValitse({ nimi, lat, lon }) -> kutsuja tallentaa
// osoitteen JA koordinaatit kerralla, jolloin geokoodausta ei tarvita.
//
// Käsin kirjoitettu osoite toimii kuten ennenkin (onChange + onBlur); silloin
// backend geokoodaa sen tallennettaessa.
//
// Haku vasta kun kirjoittaminen on tauonnut VIIVE_MS ja tekstiä on vähintään
// MIN_MERKKEJA; edellinen keskeneräinen haku perutaan.

const VIIVE_MS = 350;
const MIN_MERKKEJA = 3;

export default function OsoiteKentta({ value, onChange, onValitse, onBlur, w = 220, ph = "Katu 1, Kaupunki" }) {
  const [ehdotukset, setEhdotukset] = useState([]);
  const [auki, setAuki] = useState(false);
  const [korostettu, setKorostettu] = useState(-1);
  const [tila, setTila] = useState("lepo"); // lepo | haetaan | virhe
  const ajastin = useRef(null);
  const keskeytys = useRef(null);
  const kirjoitettu = useRef(false); // haetaan vain käyttäjän kirjoittaessa, ei kun arvo tulee ulkoa

  useEffect(() => {
    clearTimeout(ajastin.current);
    if (!kirjoitettu.current) return;
    const q = (value || "").trim();
    if (q.length < MIN_MERKKEJA) return; // lista suljetaan jo onChangessa
    ajastin.current = setTimeout(async () => {
      keskeytys.current?.abort();
      const ohjain = new AbortController();
      keskeytys.current = ohjain;
      setTila("haetaan");
      try {
        const tulos = await api.ehdotaOsoitteita(q, ohjain.signal);
        if (ohjain.signal.aborted) return;
        setEhdotukset(tulos);
        setKorostettu(-1);
        setAuki(true);
        setTila("lepo");
      } catch (e) {
        if (e.name === "AbortError") return;
        setEhdotukset([]);
        setAuki(true);
        setTila("virhe");
      }
    }, VIIVE_MS);
    return () => clearTimeout(ajastin.current);
  }, [value]);

  useEffect(() => () => keskeytys.current?.abort(), []);

  const valitse = (e) => {
    kirjoitettu.current = false;
    keskeytys.current?.abort();
    setAuki(false);
    setEhdotukset([]);
    onValitse(e);
  };

  const nappain = (e) => {
    if (!auki || ehdotukset.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setKorostettu((i) => (i + 1) % ehdotukset.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setKorostettu((i) => (i <= 0 ? ehdotukset.length - 1 : i - 1));
    } else if (e.key === "Enter" && korostettu >= 0) {
      e.preventDefault();
      valitse(ehdotukset[korostettu]);
    } else if (e.key === "Escape") {
      setAuki(false);
    }
  };

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <input
        value={value}
        placeholder={ph}
        autoComplete="off"
        role="combobox"
        aria-expanded={auki}
        aria-autocomplete="list"
        onChange={(e) => {
          kirjoitettu.current = true;
          if (e.target.value.trim().length < MIN_MERKKEJA) {
            keskeytys.current?.abort();
            setEhdotukset([]);
            setAuki(false);
            setTila("lepo");
          }
          onChange(e.target.value);
        }}
        onKeyDown={nappain}
        onFocus={() => ehdotukset.length > 0 && setAuki(true)}
        onBlur={() => {
          setAuki(false);
          onBlur?.();
        }}
        style={{
          width: w,
          fontFamily: "'IBM Plex Mono',monospace",
          fontSize: 13,
          fontWeight: 600,
          padding: "6px 8px",
          border: `2px solid ${C.line}`,
          borderRadius: 8,
          background: C.card,
          color: C.inkSolid,
        }}
      />
      {tila === "haetaan" && (
        <span
          aria-hidden
          style={{ position: "absolute", right: 8, top: 8, fontSize: 11, color: C.olive, fontFamily: "'IBM Plex Mono',monospace" }}
        >
          …
        </span>
      )}
      {auki && (
        <ul
          role="listbox"
          // mousedown ennen inputin blur-tapahtumaa: estetään blur, jotta klikkaus ehtii valita
          onMouseDown={(e) => e.preventDefault()}
          style={{
            position: "absolute",
            zIndex: 20,
            top: "calc(100% + 4px)",
            left: 0,
            minWidth: Math.max(w, 280),
            maxWidth: 420,
            margin: 0,
            padding: 4,
            listStyle: "none",
            fontFamily: "'Archivo',sans-serif",
            background: C.card,
            border: `2px solid ${C.line}`,
            borderRadius: 10,
            boxShadow: `4px 4px 0 ${C.line}`,
          }}
        >
          {tila === "virhe" && (
            <li style={{ padding: "6px 8px", fontSize: 12, color: C.rust }}>
              Osoitehaku ei vastaa juuri nyt. Kirjoita osoite käsin, niin se geokoodataan tallennettaessa.
            </li>
          )}
          {tila !== "virhe" && ehdotukset.length === 0 && (
            <li style={{ padding: "6px 8px", fontSize: 12, color: C.olive }}>
              Ei ehdotuksia. Voit kirjoittaa osoitteen käsin.
            </li>
          )}
          {ehdotukset.map((e, i) => (
            <li
              key={`${e.nimi}-${e.lat}-${e.lon}`}
              role="option"
              aria-selected={i === korostettu}
              onClick={() => valitse(e)}
              onMouseEnter={() => setKorostettu(i)}
              style={{
                padding: "6px 8px",
                borderRadius: 6,
                cursor: "pointer",
                fontSize: 13,
                lineHeight: 1.3,
                color: C.inkSolid,
                background: i === korostettu ? C.ochre + "55" : "transparent",
              }}
            >
              {e.nimi}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

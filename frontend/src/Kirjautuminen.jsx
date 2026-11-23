/* Kirjautumissivu (ROADMAP K3). POST /auth/kirjaudu → token sessionStorageen
   (istunto.js). Backend antaa kaikista epäonnistumisista saman 401-viestin,
   ja se näytetään sellaisenaan.
   Demotila (ROADMAP M2): jos backendissä on DEMO=true, lomakkeen alla on
   "Kokeile demoa" -napit, jotka kirjautuvat demokäyttäjäksi ilman salasanaa. */
import { useEffect, useState } from "react";
import { haeDemoTila, kirjaudu, kirjauduDemoon } from "./api.js";
import { tallennaIstunto } from "./istunto.js";
import { C, Nappi, KenttaOtsikolla, Kentta, vihje } from "./ui.jsx";

const ilmoitusTyyli = (vari, tausta) => ({
  border: `2px solid ${vari}`,
  background: tausta,
  borderRadius: 12,
  padding: "10px 14px",
  marginBottom: 16,
  fontFamily: "'Archivo',sans-serif",
  fontWeight: 600,
  fontSize: 13,
  color: vari,
});

const DEMONAPPI = {
  tuotanto: "Tuotantona",
  kuski: "Kuskina",
};

export default function Kirjautuminen({ onKirjautunut, ilmoitus }) {
  const [email, setEmail] = useState("");
  const [salasana, setSalasana] = useState("");
  const [virhe, setVirhe] = useState(null);
  const [lahettaa, setLahettaa] = useState(false);
  const [demoRoolit, setDemoRoolit] = useState([]);

  useEffect(() => {
    let voimassa = true;
    haeDemoTila()
      .then((tila) => {
        if (voimassa && tila.kaytossa) setDemoRoolit(tila.roolit);
      })
      .catch(() => {
        // Ei demotilaa tai backend ei vastaa: napit jäävät pois.
      });
    return () => {
      voimassa = false;
    };
  }, []);

  const kirjauduDemona = async (rooli) => {
    setLahettaa(true);
    setVirhe(null);
    try {
      const istunto = tallennaIstunto(await kirjauduDemoon(rooli));
      onKirjautunut(istunto.kayttaja);
    } catch (err) {
      setVirhe(err.message);
    } finally {
      setLahettaa(false);
    }
  };

  const laheta = async (e) => {
    e.preventDefault();
    if (!email.trim() || !salasana) {
      setVirhe("Anna sähköposti ja salasana.");
      return;
    }
    setLahettaa(true);
    setVirhe(null);
    try {
      const vastaus = await kirjaudu(email.trim(), salasana);
      const istunto = tallennaIstunto(vastaus);
      onKirjautunut(istunto.kayttaja);
    } catch (err) {
      setVirhe(err.message);
      setSalasana("");
    } finally {
      setLahettaa(false);
    }
  };

  // Kentät venyvät kortin levyisiksi (myös puhelimella).
  const kentanLeveys = "100%";

  return (
    <div style={{ maxWidth: 420, margin: "0 auto" }}>
      <section
        style={{
          background: C.card,
          border: `2px solid ${C.line}`,
          borderRadius: 16,
          boxShadow: `5px 5px 0 ${C.line}`,
          padding: "22px 20px",
        }}
      >
        <h2 style={{ fontFamily: "'Fraunces',serif", fontWeight: 700, fontSize: 24, margin: "0 0 16px", color: C.inkSolid }}>
          Kirjaudu sisään
        </h2>

        {ilmoitus && !virhe && <div style={ilmoitusTyyli(C.teal, "#DCE8E2")}>{ilmoitus}</div>}
        {virhe && (
          <div role="alert" style={ilmoitusTyyli(C.rust, "#F7DFD2")}>
            ⚠ {virhe}
          </div>
        )}

        <form onSubmit={laheta} noValidate style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <KenttaOtsikolla id="kirjaudu-email" otsikko="Sähköposti" style={{ display: "flex" }}>
            <Kentta id="kirjaudu-email" type="email" value={email} onChange={setEmail} w={kentanLeveys} autoComplete="username" />
          </KenttaOtsikolla>
          <KenttaOtsikolla id="kirjaudu-salasana" otsikko="Salasana" style={{ display: "flex" }}>
            <Kentta
              id="kirjaudu-salasana"
              type="password"
              value={salasana}
              onChange={setSalasana}
              w={kentanLeveys}
              autoComplete="current-password"
            />
          </KenttaOtsikolla>
          <Nappi type="submit" variant="orange" disabled={lahettaa} style={{ alignSelf: "flex-start", marginTop: 4 }}>
            {lahettaa ? "Kirjaudutaan…" : "Kirjaudu"}
          </Nappi>
        </form>

        <p style={vihje}>
          Istunto päättyy, kun suljet välilehden, tai viimeistään 12 tunnin kuluttua. Tunnukset antaa tuotanto.
        </p>

        {demoRoolit.length > 0 && (
          <div style={{ borderTop: `2px dashed ${C.line}`, marginTop: 18, paddingTop: 16 }}>
            <h3 style={{ fontFamily: "'Fraunces',serif", fontWeight: 700, fontSize: 18, margin: "0 0 6px", color: C.inkSolid }}>
              Kokeile demoa
            </h3>
            <p style={{ ...vihje, marginTop: 0 }}>
              Kirjaudu ilman tunnuksia valmiiseen demotuotantoon. Demodata palautuu alkutilaan aika ajoin.
            </p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 }}>
              {demoRoolit.map((rooli) => (
                <Nappi key={rooli} variant="ghost" disabled={lahettaa} onClick={() => kirjauduDemona(rooli)}>
                  {DEMONAPPI[rooli] ?? rooli}
                </Nappi>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

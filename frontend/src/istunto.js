/* Kirjautumisistunto (ROADMAP K3).

   Token ja kirjautunut käyttäjä pidetään muistissa ja sessionStoragessa.
   sessionStorage (ei localStorage) tarkoituksella: välilehden sulkeminen
   kirjaa ulos, mutta sivun päivitys ei. Selain voi estää tallennuksen
   (yksityinen ikkuna, estetyt evästeet), joten jokainen kutsu on try/catchissa
   ja sovellus toimii silloin pelkän muistin varassa. */

const AVAIN = "ajuri.istunto";

let nykyinen = lueTallennettu();
let vanhenemisKasittelija = null;

function lueTallennettu() {
  try {
    const raaka = sessionStorage.getItem(AVAIN);
    if (!raaka) return null;
    const data = JSON.parse(raaka);
    if (!data?.token || !data?.kayttaja) return null;
    // Token vanhenee backendissä joka tapauksessa; tämä vain säästää yhden
    // turhan pyynnön, jos välilehti on ollut auki yli voimassaoloajan.
    if (data.vanhenee && Date.now() >= data.vanhenee) return null;
    return data;
  } catch {
    return null;
  }
}

export function haeIstunto() {
  return nykyinen;
}

export function haeToken() {
  return nykyinen?.token ?? null;
}

// vastaus = POST /auth/kirjaudu -vastaus: { access_token, voimassa_s, kayttaja }
export function tallennaIstunto(vastaus) {
  nykyinen = {
    token: vastaus.access_token,
    kayttaja: vastaus.kayttaja,
    vanhenee: Date.now() + vastaus.voimassa_s * 1000,
  };
  try {
    sessionStorage.setItem(AVAIN, JSON.stringify(nykyinen));
  } catch {
    // tallennus estetty: istunto säilyy vain tämän sivulatauksen ajan
  }
  return nykyinen;
}

export function paivitaKayttaja(kayttaja) {
  if (!nykyinen) return;
  nykyinen = { ...nykyinen, kayttaja };
  try {
    sessionStorage.setItem(AVAIN, JSON.stringify(nykyinen));
  } catch {
    // ks. yllä
  }
}

export function tyhjennaIstunto() {
  nykyinen = null;
  try {
    sessionStorage.removeItem(AVAIN);
  } catch {
    // ks. yllä
  }
}

// App rekisteröi tämän: api.js kutsuu sitä, kun backend vastaa 401 pyyntöön,
// jossa token oli mukana (token vanhentunut tai käyttäjä passivoitu).
export function asetaVanhenemisKasittelija(fn) {
  vanhenemisKasittelija = fn;
}

export function istuntoVanheni() {
  tyhjennaIstunto();
  vanhenemisKasittelija?.();
}

export const ROOLI_NIMI = {
  tuotanto: "Tuotanto",
  koordi: "Koordinaattori",
  kuski: "Kuski",
};

// KUSKI saa vain lukea (backend palauttaa muokkauksista 403:n).
export const voiMuokata = (kayttaja) => !!kayttaja && kayttaja.rooli !== "kuski";

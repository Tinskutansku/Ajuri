# Ajolista — demo-frontti

Vite + React -demo optimoijaservicelle. Yksi näkymä: valitse kuvauspäivä,
paina "Optimoi", katso tulos (per kuski aikajana + keikat, ylityömerkintä,
sijoittamattomat, skenaariovertailu). Ei kirjautumista, ei muokkausnäkymiä.

Visuaalinen tyyli ja komponenttirakenne on poimittu
`docs/ajolista_ui_luonnos_v2.jsx`-luonnoksesta.

## Käynnistys

Vaatii backendin pyörimässä (ks. juuren README.md) osoitteessa
`http://localhost:8000`, CORS sallittuna porttiin 5173.

```
cp .env.example .env
npm install
npm run dev
```

Avaa http://localhost:5173. Jos kuvauspäiviä ei löydy, aja backendissä
`python -m app.seed`.

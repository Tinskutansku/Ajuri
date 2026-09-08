from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    ajoneuvo,
    henkilo,
    keikat,
    kuski,
    kuvauspaiva,
    lokaatio,
    optimointi,
    paiva_henkilo,
    paiva_kuski,
    paiva_lokaatio,
    tehtava,
    tehtava_generointi,
    tuotanto,
    versiot,
)

app = FastAPI(title="Ajolista API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tuotanto.router)
app.include_router(henkilo.router)
app.include_router(kuski.router)
app.include_router(ajoneuvo.router)
app.include_router(lokaatio.router)
app.include_router(kuvauspaiva.router)
app.include_router(paiva_lokaatio.router)
app.include_router(paiva_henkilo.router)
app.include_router(paiva_kuski.router)
app.include_router(tehtava.router)
app.include_router(tehtava_generointi.router)
app.include_router(versiot.router)
app.include_router(keikat.router)
app.include_router(optimointi.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

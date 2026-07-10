from fastapi import FastAPI

from app.routers import ajoneuvo, henkilo, kuski, lokaatio, optimointi, tuotanto

app = FastAPI(title="Ajolista API")

app.include_router(tuotanto.router)
app.include_router(henkilo.router)
app.include_router(kuski.router)
app.include_router(ajoneuvo.router)
app.include_router(lokaatio.router)
app.include_router(optimointi.router)


@app.get("/health")
async def health():
    return {"status": "ok"}

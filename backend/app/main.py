from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import close_db_pool, init_db_pool, init_schema
from app.routes import accounts, reports, transactions


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Inicialización de conexión a PostgreSQL
    pool = await init_db_pool(settings.DATABASE_URL)
    await init_schema(pool)
    yield
    # Cierre de conexiones
    await close_db_pool()


app = FastAPI(
    title="Double-Entry Ledger API",
    description="Motor contable de doble partida con garantías de integridad en PostgreSQL",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Idempotent-Replay"],
)

app.include_router(accounts.router, prefix="/api")
app.include_router(transactions.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/api/health", tags=["Salud"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "double-entry-ledger"}

from collections.abc import AsyncIterator
from datetime import datetime

import asyncpg
from fastapi import APIRouter, Depends, Query

from app.db import get_pool
from app.models import TrialBalanceReport
from app.service import get_trial_balance

router = APIRouter(prefix="/reports", tags=["Informes Contables"])


async def get_db_conn() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@router.get("/trial-balance", response_model=TrialBalanceReport)
async def api_get_trial_balance(
    as_of: datetime | None = Query(None, description="Fecha de corte para el balance"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TrialBalanceReport:
    """Genera el Balance de Sumas y Saldos (Trial Balance).

    Permite auditar que la suma global de débitos es idéntica a la suma global de créditos.
    """
    return await get_trial_balance(conn, as_of=as_of)

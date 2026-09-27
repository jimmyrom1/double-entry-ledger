from collections.abc import AsyncIterator

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.db import get_pool
from app.models import (
    TransactionCreate,
    TransactionResponse,
)
from app.service import (
    AccountNotFoundError,
    InsufficientFundsError,
    TransactionAlreadyReversedError,
    TransactionNotFoundError,
    UnbalancedTransactionError,
    create_transaction,
    get_transaction,
    list_transactions,
    reverse_transaction,
)

router = APIRouter(prefix="/transactions", tags=["Transacciones"])


async def get_db_conn() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


class ReversalRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=128)
    reason: str | None = None


@router.post("", response_model=TransactionResponse)
async def api_create_transaction(
    tx_in: TransactionCreate,
    response: Response,
    idempotency_header: str | None = Header(None, alias="Idempotency-Key"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TransactionResponse:
    """Registra una transacción contable inmutable de doble partida.

    Garantiza:
    - Suma cero (Debe == Haber) por diseño y mediante constraint trigger diferido en PostgreSQL.
    - Idempotencia estricta vía Idempotency-Key.
    - Prevención de saldos negativos concurrentes mediante SELECT ... FOR UPDATE ordenado.
    """
    if idempotency_header and not tx_in.idempotency_key:
        tx_in.idempotency_key = idempotency_header

    try:
        async with conn.transaction():
            tx, is_replay = await create_transaction(conn, tx_in)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    except UnbalancedTransactionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e
    except asyncpg.CheckViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Violación de regla contable en BD: {e}",
        ) from e

    if is_replay:
        response.status_code = status.HTTP_200_OK
        response.headers["X-Idempotent-Replay"] = "true"
    else:
        response.status_code = status.HTTP_201_CREATED

    return tx


@router.get("", response_model=list[TransactionResponse])
async def api_list_transactions(
    limit: int = 50,
    offset: int = 0,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> list[TransactionResponse]:
    """Lista el libro diario de transacciones contables."""
    return await list_transactions(conn, limit=limit, offset=offset)


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def api_get_transaction(
    transaction_id: int,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TransactionResponse:
    """Obtiene el detalle completo de un asiento contable y sus líneas."""
    tx = await get_transaction(conn, transaction_id)
    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transacción con ID {transaction_id} no encontrada",
        )
    return tx


@router.post("/{transaction_id}/reversal", response_model=TransactionResponse)
async def api_reverse_transaction(
    transaction_id: int,
    payload: ReversalRequest,
    response: Response,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> TransactionResponse:
    """Revierte un asiento contable emitiendo una transacción compensatoria inversa."""
    try:
        async with conn.transaction():
            tx, is_replay = await reverse_transaction(
                conn,
                original_tx_id=transaction_id,
                idempotency_key=payload.idempotency_key,
                reason=payload.reason,
            )
    except TransactionNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except TransactionAlreadyReversedError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e)) from e
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e)) from e

    if is_replay:
        response.status_code = status.HTTP_200_OK
        response.headers["X-Idempotent-Replay"] = "true"
    else:
        response.status_code = status.HTTP_201_CREATED

    return tx

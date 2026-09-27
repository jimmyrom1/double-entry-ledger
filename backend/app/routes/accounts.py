from collections.abc import AsyncIterator

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_pool
from app.models import (
    AccountCreate,
    AccountResponse,
    AccountStatementResponse,
)
from app.service import (
    AccountNotFoundError,
    DuplicateAccountCodeError,
    create_account,
    get_account,
    get_account_statement,
    list_accounts,
)

router = APIRouter(prefix="/accounts", tags=["Cuentas Contables"])


async def get_db_conn() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def api_create_account(
    account_in: AccountCreate,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AccountResponse:
    """Crea una nueva cuenta en el plan contable."""
    try:
        return await create_account(conn, account_in)
    except DuplicateAccountCodeError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.get("", response_model=list[AccountResponse])
async def api_list_accounts(
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> list[AccountResponse]:
    """Lista todas las cuentas del libro mayor con sus saldos calculados."""
    return await list_accounts(conn)


@router.get("/{account_id}", response_model=AccountResponse)
async def api_get_account(
    account_id: int,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AccountResponse:
    """Obtiene el detalle y saldo de una cuenta específica."""
    account = await get_account(conn, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cuenta con ID {account_id} no encontrada",
        )
    return account


@router.get("/{account_id}/statement", response_model=AccountStatementResponse)
async def api_get_account_statement(
    account_id: int,
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AccountStatementResponse:
    """Obtiene el extracto de cuenta con su saldo cronológico acumulado."""
    try:
        return await get_account_statement(conn, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

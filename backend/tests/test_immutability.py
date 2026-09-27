import asyncpg
import httpx
import pytest


@pytest.mark.asyncio
async def test_posting_immutability_triggers(client: httpx.AsyncClient, db_pool: asyncpg.Pool):
    # Crear cuentas y una transacción válida
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET"},
        )
    ).json()

    ventas = (
        await client.post(
            "/api/accounts",
            json={"code": "7000", "name": "Ventas", "type": "REVENUE"},
        )
    ).json()

    tx = (
        await client.post(
            "/api/transactions",
            json={
                "idempotency_key": "tx-immutable-1",
                "description": "Venta inmutable",
                "postings": [
                    {"account_id": caja["id"], "direction": "DEBIT", "amount": 100.00},
                    {"account_id": ventas["id"], "direction": "CREDIT", "amount": 100.00},
                ],
            },
        )
    ).json()

    posting_id = tx["postings"][0]["id"]
    tx_id = tx["id"]

    async with db_pool.acquire() as conn:
        # 1. Intentar hacer un UPDATE directo en postings debe lanzar error de integridad en BD
        with pytest.raises(asyncpg.IntegrityConstraintViolationError, match="strictly immutable"):
            await conn.execute(
                "UPDATE postings SET amount = 999.00 WHERE id = $1",
                posting_id,
            )

        # 2. Intentar hacer un DELETE directo en postings debe lanzar error de integridad en BD
        with pytest.raises(asyncpg.IntegrityConstraintViolationError, match="strictly immutable"):
            await conn.execute(
                "DELETE FROM postings WHERE id = $1",
                posting_id,
            )

        # 3. Intentar hacer un DELETE directo en transactions debe lanzar error
        with pytest.raises(asyncpg.IntegrityConstraintViolationError, match="strictly immutable"):
            await conn.execute(
                "DELETE FROM transactions WHERE id = $1",
                tx_id,
            )

        # 4. Intentar alterar campos inmutables de la transacción (como description)
        with pytest.raises(asyncpg.IntegrityConstraintViolationError, match="fields are immutable"):
            await conn.execute(
                "UPDATE transactions SET description = 'Alterado' WHERE id = $1",
                tx_id,
            )


@pytest.mark.asyncio
async def test_database_deferrable_zero_sum_constraint(
    client: httpx.AsyncClient, db_pool: asyncpg.Pool
):
    """Verifica que si se intenta saltar la API insertando directamente en PostgreSQL,

    el constraint trigger diferido 'trg_check_transaction_balanced' bloquea el COMMIT.
    """
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET"},
        )
    ).json()

    ventas = (
        await client.post(
            "/api/accounts",
            json={"code": "7000", "name": "Ventas", "type": "REVENUE"},
        )
    ).json()

    async with db_pool.acquire() as conn:
        # Caso 1: menos de 2 líneas
        with pytest.raises(asyncpg.CheckViolationError, match="must contain at least 2 postings"):
            async with conn.transaction():
                tx_row = await conn.fetchrow(
                    """
                    INSERT INTO transactions (idempotency_key, description)
                    VALUES ('tx-direct-sql-single', 'Asiento con una sola pata')
                    RETURNING id
                    """
                )
                await conn.execute(
                    """
                    INSERT INTO postings (transaction_id, account_id, direction, amount)
                    VALUES ($1, $2, 'DEBIT', 50.00)
                    """,
                    tx_row["id"],
                    caja["id"],
                )

        # Caso 2: 2 líneas descuadradas (Debe 50 vs Haber 40)
        with pytest.raises(asyncpg.CheckViolationError, match="unbalanced"):
            async with conn.transaction():
                tx_row = await conn.fetchrow(
                    """
                    INSERT INTO transactions (idempotency_key, description)
                    VALUES ('tx-direct-sql-unbalanced', 'Asiento con descuadre en importes')
                    RETURNING id
                    """
                )
                await conn.execute(
                    """
                    INSERT INTO postings (transaction_id, account_id, direction, amount)
                    VALUES ($1, $2, 'DEBIT', 50.00)
                    """,
                    tx_row["id"],
                    caja["id"],
                )
                await conn.execute(
                    """
                    INSERT INTO postings (transaction_id, account_id, direction, amount)
                    VALUES ($1, $2, 'CREDIT', 40.00)
                    """,
                    tx_row["id"],
                    ventas["id"],
                )

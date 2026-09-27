import asyncio
from decimal import Decimal

import asyncpg

from app.config import settings
from app.models import (
    AccountCreate,
    AccountType,
    PostingCreate,
    PostingDirection,
    TransactionCreate,
)
from app.service import create_account, create_transaction


async def seed_data(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        # Comprobar si ya existen cuentas
        count = await conn.fetchval("SELECT COUNT(*) FROM accounts")
        if count and count > 0:
            print("La base de datos ya contiene cuentas. Omitiendo seed.")
            return

        print("Poblando plan contable y transacciones de demostración...")

        # 1. Crear cuentas
        accounts_to_create = [
            AccountCreate(
                code="1000",
                name="Caja en Efectivo",
                type=AccountType.ASSET,
                allow_negative=False,
            ),
            AccountCreate(
                code="1200",
                name="Cuenta Corriente Bancaria",
                type=AccountType.ASSET,
                allow_negative=False,
            ),
            AccountCreate(
                code="4300",
                name="Clientes y Cuentas por Cobrar",
                type=AccountType.ASSET,
                allow_negative=False,
            ),
            AccountCreate(
                code="4000",
                name="Proveedores y Cuentas por Pagar",
                type=AccountType.LIABILITY,
                allow_negative=False,
            ),
            AccountCreate(
                code="4770",
                name="H.P. IVA Repercutido (21%)",
                type=AccountType.LIABILITY,
                allow_negative=True,
            ),
            AccountCreate(
                code="4720",
                name="H.P. IVA Soportado (21%)",
                type=AccountType.ASSET,
                allow_negative=True,
            ),
            AccountCreate(
                code="3000",
                name="Capital Social Inicial",
                type=AccountType.EQUITY,
                allow_negative=True,
            ),
            AccountCreate(
                code="7000",
                name="Ventas de Servicios SaaS",
                type=AccountType.REVENUE,
                allow_negative=True,
            ),
            AccountCreate(
                code="6000",
                name="Compras y Licencias Cloud",
                type=AccountType.EXPENSE,
                allow_negative=True,
            ),
            AccountCreate(
                code="6280",
                name="Suministros de Oficina",
                type=AccountType.EXPENSE,
                allow_negative=True,
            ),
        ]

        created_accounts: dict[str, int] = {}
        for acc_in in accounts_to_create:
            acc = await create_account(conn, acc_in)
            created_accounts[acc.code] = acc.id
            print(f"  + Cuenta creada: [{acc.code}] {acc.name}")

        # 2. Registrar transacciones demostrativas
        demo_txs = [
            TransactionCreate(
                idempotency_key="demo-seed-001",
                description="Constitución y aportación de capital inicial en banco",
                postings=[
                    PostingCreate(
                        account_id=created_accounts["1200"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("15000.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["3000"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("15000.0000"),
                    ),
                ],
            ),
            TransactionCreate(
                idempotency_key="demo-seed-002",
                description="Retirada para fondo de caja menor en efectivo",
                postings=[
                    PostingCreate(
                        account_id=created_accounts["1000"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("500.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["1200"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("500.0000"),
                    ),
                ],
            ),
            TransactionCreate(
                idempotency_key="demo-seed-003",
                description="Emisión de factura F-2026-001 a Cliente por consultoría",
                postings=[
                    PostingCreate(
                        account_id=created_accounts["4300"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("2420.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["7000"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("2000.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["4770"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("420.0000"),
                    ),
                ],
            ),
            TransactionCreate(
                idempotency_key="demo-seed-004",
                description="Factura de proveedor por servidores cloud GCP",
                postings=[
                    PostingCreate(
                        account_id=created_accounts["6000"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("800.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["4720"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("168.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["4000"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("968.0000"),
                    ),
                ],
            ),
            TransactionCreate(
                idempotency_key="demo-seed-005",
                description="Cobro por transferencia bancaria de la factura F-2026-001",
                postings=[
                    PostingCreate(
                        account_id=created_accounts["1200"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("2420.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["4300"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("2420.0000"),
                    ),
                ],
            ),
            TransactionCreate(
                idempotency_key="demo-seed-006",
                description="Pago bancario a proveedor cloud",
                postings=[
                    PostingCreate(
                        account_id=created_accounts["4000"],
                        direction=PostingDirection.DEBIT,
                        amount=Decimal("968.0000"),
                    ),
                    PostingCreate(
                        account_id=created_accounts["1200"],
                        direction=PostingDirection.CREDIT,
                        amount=Decimal("968.0000"),
                    ),
                ],
            ),
        ]

        async with conn.transaction():
            for tx_data in demo_txs:
                tx, _ = await create_transaction(conn, tx_data)
                print(f"  + Asiento contable registrado #{tx.id}: {tx.description}")

        print("Demostración cargada exitosamente.")


async def main():
    pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
    await seed_data(pool)
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

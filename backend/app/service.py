from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal

import asyncpg

from app.models import (
    AccountCreate,
    AccountResponse,
    AccountStatementItem,
    AccountStatementResponse,
    AccountType,
    PostingCreate,
    PostingDirection,
    PostingResponse,
    TransactionCreate,
    TransactionResponse,
    TransactionStatus,
    TrialBalanceLine,
    TrialBalanceReport,
)


class LedgerError(Exception):
    """Excepción base para errores del ledger."""


class AccountNotFoundError(LedgerError):
    pass


class DuplicateAccountCodeError(LedgerError):
    pass


class InsufficientFundsError(LedgerError):
    pass


class TransactionNotFoundError(LedgerError):
    pass


class TransactionAlreadyReversedError(LedgerError):
    pass


class UnbalancedTransactionError(LedgerError):
    pass


class ImmutableLedgerError(LedgerError):
    pass


async def create_account(conn: asyncpg.Connection, data: AccountCreate) -> AccountResponse:
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO accounts (code, name, type, currency, allow_negative)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, code, name, type, currency, allow_negative, created_at
            """,
            data.code,
            data.name,
            data.type.value,
            data.currency,
            data.allow_negative,
        )
    except asyncpg.UniqueViolationError as e:
        raise DuplicateAccountCodeError(f"Ya existe una cuenta con el código '{data.code}'") from e

    return AccountResponse(
        id=row["id"],
        code=row["code"],
        name=row["name"],
        type=AccountType(row["type"]),
        currency=row["currency"],
        allow_negative=row["allow_negative"],
        created_at=row["created_at"],
        balance=Decimal("0.0000"),
        total_debit=Decimal("0.0000"),
        total_credit=Decimal("0.0000"),
    )


async def get_account(conn: asyncpg.Connection, account_id: int) -> AccountResponse | None:
    row = await conn.fetchrow(
        """
        SELECT account_id, code, name, type, currency, allow_negative,
               total_debit, total_credit, balance, created_at
        FROM account_balances
        WHERE account_id = $1
        """,
        account_id,
    )
    if not row:
        return None

    return AccountResponse(
        id=row["account_id"],
        code=row["code"],
        name=row["name"],
        type=AccountType(row["type"]),
        currency=row["currency"],
        allow_negative=row["allow_negative"],
        created_at=row["created_at"],
        balance=Decimal(str(row["balance"])),
        total_debit=Decimal(str(row["total_debit"])),
        total_credit=Decimal(str(row["total_credit"])),
    )


async def list_accounts(conn: asyncpg.Connection) -> list[AccountResponse]:
    rows = await conn.fetch(
        """
        SELECT account_id, code, name, type, currency, allow_negative,
               total_debit, total_credit, balance, created_at
        FROM account_balances
        ORDER BY code ASC
        """
    )
    return [
        AccountResponse(
            id=r["account_id"],
            code=r["code"],
            name=r["name"],
            type=AccountType(r["type"]),
            currency=r["currency"],
            allow_negative=r["allow_negative"],
            created_at=r["created_at"],
            balance=Decimal(str(r["balance"])),
            total_debit=Decimal(str(r["total_debit"])),
            total_credit=Decimal(str(r["total_credit"])),
        )
        for r in rows
    ]


async def _fetch_transaction_with_postings(
    conn: asyncpg.Connection, tx_id: int
) -> TransactionResponse | None:
    tx_row = await conn.fetchrow(
        """
        SELECT id, idempotency_key, description, posted_at, status, reversal_of_id, created_at
        FROM transactions
        WHERE id = $1
        """,
        tx_id,
    )
    if not tx_row:
        return None

    posting_rows = await conn.fetch(
        """
        SELECT p.id, p.transaction_id, p.account_id, p.direction, p.amount, p.created_at,
               a.code AS account_code, a.name AS account_name
        FROM postings p
        JOIN accounts a ON a.id = p.account_id
        WHERE p.transaction_id = $1
        ORDER BY p.id ASC
        """,
        tx_id,
    )

    return TransactionResponse(
        id=tx_row["id"],
        idempotency_key=tx_row["idempotency_key"],
        description=tx_row["description"],
        posted_at=tx_row["posted_at"],
        status=TransactionStatus(tx_row["status"]),
        reversal_of_id=tx_row["reversal_of_id"],
        created_at=tx_row["created_at"],
        postings=[
            PostingResponse(
                id=p["id"],
                transaction_id=p["transaction_id"],
                account_id=p["account_id"],
                account_code=p["account_code"],
                account_name=p["account_name"],
                direction=PostingDirection(p["direction"]),
                amount=Decimal(str(p["amount"])),
                created_at=p["created_at"],
            )
            for p in posting_rows
        ],
    )


async def create_transaction(
    conn: asyncpg.Connection,
    data: TransactionCreate,
    reversal_of_id: int | None = None,
) -> tuple[TransactionResponse, bool]:
    """Crea una transacción contable atómica con verificación pesimista anti-descubierto.

    Retorna (TransactionResponse, is_idempotent_replay).
    """
    # 1. Comprobación de idempotencia
    existing_tx = await conn.fetchrow(
        "SELECT id FROM transactions WHERE idempotency_key = $1",
        data.idempotency_key,
    )
    if existing_tx:
        full_tx = await _fetch_transaction_with_postings(conn, existing_tx["id"])
        if full_tx:
            return full_tx, True

    # 2. Bloqueo ordenado por ID de todas las cuentas involucradas para evitar deadlocks
    account_ids = sorted({p.account_id for p in data.postings})
    locked_rows = await conn.fetch(
        """
        SELECT id, code, name, type, allow_negative
        FROM accounts
        WHERE id = ANY($1)
        ORDER BY id ASC
        FOR UPDATE
        """,
        account_ids,
    )

    if len(locked_rows) != len(account_ids):
        found_ids = {r["id"] for r in locked_rows}
        missing_ids = set(account_ids) - found_ids
        raise AccountNotFoundError(f"Cuentas no encontradas: {missing_ids}")

    accounts_by_id = {r["id"]: r for r in locked_rows}

    # 3. Control de saldo mínimo para cuentas que no permiten saldo negativo
    deltas: dict[int, Decimal] = defaultdict(lambda: Decimal("0.0000"))
    for p in data.postings:
        acc = accounts_by_id[p.account_id]
        acc_type = acc["type"]
        # En cuentas de Activo y Gasto, Debe suma y Haber resta
        if acc_type in (AccountType.ASSET.value, AccountType.EXPENSE.value):
            delta = p.amount if p.direction == PostingDirection.DEBIT else -p.amount
        else:
            # En Pasivo, Patrimonio e Ingresos, Haber suma y Debe resta
            delta = p.amount if p.direction == PostingDirection.CREDIT else -p.amount
        deltas[p.account_id] += delta

    for acc_id, delta in deltas.items():
        acc = accounts_by_id[acc_id]
        if not acc["allow_negative"]:
            current_bal_row = await conn.fetchrow(
                """
                SELECT
                    CASE
                        WHEN type IN ('ASSET', 'EXPENSE') THEN
                            COALESCE(
                                SUM(
                                    CASE
                                        WHEN p.direction = 'DEBIT' THEN p.amount
                                        ELSE -p.amount
                                    END
                                ),
                                0
                            )
                        ELSE
                            COALESCE(
                                SUM(
                                    CASE
                                        WHEN p.direction = 'CREDIT' THEN p.amount
                                        ELSE -p.amount
                                    END
                                ),
                                0
                            )
                    END AS balance
                FROM accounts a
                LEFT JOIN postings p ON a.id = p.account_id
                WHERE a.id = $1
                GROUP BY a.id, a.type
                """,
                acc_id,
            )
            current_balance = (
                Decimal(str(current_bal_row["balance"])) if current_bal_row else Decimal("0.0000")
            )
            projected_balance = current_balance + delta
            if projected_balance < Decimal("0.0000"):
                raise InsufficientFundsError(
                    f"La cuenta {acc['code']} ('{acc['name']}') no permite saldo negativo. "
                    f"Saldo actual: {current_balance}, saldo resultante: {projected_balance}"
                )

    # 4. Inserción de cabecera de transacción
    try:
        tx_row = await conn.fetchrow(
            """
            INSERT INTO transactions (idempotency_key, description, posted_at, reversal_of_id)
            VALUES ($1, $2, COALESCE($3, now()), $4)
            RETURNING id, idempotency_key, description, posted_at, status,
                      reversal_of_id, created_at
            """,
            data.idempotency_key,
            data.description,
            data.posted_at,
            reversal_of_id,
        )
    except asyncpg.UniqueViolationError:
        # Carrera de idempotencia simultánea
        existing = await conn.fetchrow(
            "SELECT id FROM transactions WHERE idempotency_key = $1", data.idempotency_key
        )
        if existing:
            full_tx = await _fetch_transaction_with_postings(conn, existing["id"])
            if full_tx:
                return full_tx, True
        raise

    tx_id = tx_row["id"]

    # 5. Inserción de líneas (postings)
    for p in data.postings:
        await conn.execute(
            """
            INSERT INTO postings (transaction_id, account_id, direction, amount)
            VALUES ($1, $2, $3, $4)
            """,
            tx_id,
            p.account_id,
            p.direction.value,
            p.amount,
        )

    full_tx = await _fetch_transaction_with_postings(conn, tx_id)
    if not full_tx:
        raise RuntimeError("Fallo inesperado al recuperar la transacción recién creada")

    return full_tx, False


async def reverse_transaction(
    conn: asyncpg.Connection,
    original_tx_id: int,
    idempotency_key: str,
    reason: str | None = None,
) -> tuple[TransactionResponse, bool]:
    """Crea una transacción compensatoria inversa y marca la original como REVERSED."""
    # Verificar idempotencia primero
    existing = await conn.fetchrow(
        "SELECT id FROM transactions WHERE idempotency_key = $1", idempotency_key
    )
    if existing:
        full_tx = await _fetch_transaction_with_postings(conn, existing["id"])
        if full_tx:
            return full_tx, True

    orig_tx = await _fetch_transaction_with_postings(conn, original_tx_id)
    if not orig_tx:
        raise TransactionNotFoundError(
            f"Transacción original con ID {original_tx_id} no encontrada"
        )

    if orig_tx.status == TransactionStatus.REVERSED:
        raise TransactionAlreadyReversedError(
            f"La transacción {original_tx_id} ya se encuentra revertida"
        )

    # Invertir postings: DEBIT -> CREDIT y CREDIT -> DEBIT
    reversed_postings: list[PostingCreate] = []
    for p in orig_tx.postings:
        inverted_dir = (
            PostingDirection.CREDIT
            if p.direction == PostingDirection.DEBIT
            else PostingDirection.DEBIT
        )
        reversed_postings.append(
            PostingCreate(
                account_id=p.account_id,
                direction=inverted_dir,
                amount=p.amount,
            )
        )

    desc = reason or f"Reversión de transacción #{orig_tx.id}: {orig_tx.description}"
    reversal_data = TransactionCreate(
        idempotency_key=idempotency_key,
        description=desc,
        posted_at=datetime.now(UTC),
        postings=reversed_postings,
    )

    reversal_tx, is_replay = await create_transaction(
        conn, reversal_data, reversal_of_id=original_tx_id
    )

    # Marcar original como REVERSED
    await conn.execute(
        "UPDATE transactions SET status = 'REVERSED' WHERE id = $1",
        original_tx_id,
    )

    return reversal_tx, is_replay


async def get_transaction(conn: asyncpg.Connection, tx_id: int) -> TransactionResponse | None:
    return await _fetch_transaction_with_postings(conn, tx_id)


async def list_transactions(
    conn: asyncpg.Connection, limit: int = 50, offset: int = 0
) -> list[TransactionResponse]:
    tx_rows = await conn.fetch(
        """
        SELECT id
        FROM transactions
        ORDER BY posted_at DESC, id DESC
        LIMIT $1 OFFSET $2
        """,
        limit,
        offset,
    )
    results: list[TransactionResponse] = []
    for r in tx_rows:
        tx = await _fetch_transaction_with_postings(conn, r["id"])
        if tx:
            results.append(tx)
    return results


async def get_trial_balance(
    conn: asyncpg.Connection, as_of: datetime | None = None
) -> TrialBalanceReport:
    """Genera el balance de sumas y saldos para verificar el cuadre integral del libro contable."""
    timestamp = as_of or datetime.now(UTC)
    rows = await conn.fetch(
        """
        SELECT
            a.id AS account_id,
            a.code,
            a.name,
            a.type,
            COALESCE(
                SUM(CASE WHEN p.direction = 'DEBIT' THEN p.amount ELSE 0 END), 0
            ) AS total_debit,
            COALESCE(
                SUM(CASE WHEN p.direction = 'CREDIT' THEN p.amount ELSE 0 END), 0
            ) AS total_credit
        FROM accounts a
        LEFT JOIN postings p ON a.id = p.account_id AND p.created_at <= $1
        GROUP BY a.id, a.code, a.name, a.type
        ORDER BY a.code ASC
        """,
        timestamp,
    )

    lines: list[TrialBalanceLine] = []
    total_debits = Decimal("0.0000")
    total_credits = Decimal("0.0000")
    total_debit_balance = Decimal("0.0000")
    total_credit_balance = Decimal("0.0000")

    for r in rows:
        td = Decimal(str(r["total_debit"]))
        tc = Decimal(str(r["total_credit"]))
        total_debits += td
        total_credits += tc

        if td > tc:
            db_bal = td - tc
            cr_bal = Decimal("0.0000")
        else:
            db_bal = Decimal("0.0000")
            cr_bal = tc - td

        total_debit_balance += db_bal
        total_credit_balance += cr_bal

        lines.append(
            TrialBalanceLine(
                account_id=r["account_id"],
                code=r["code"],
                name=r["name"],
                type=AccountType(r["type"]),
                total_debit=td,
                total_credit=tc,
                debit_balance=db_bal,
                credit_balance=cr_bal,
            )
        )

    is_balanced = (total_debits == total_credits) and (total_debit_balance == total_credit_balance)

    return TrialBalanceReport(
        as_of=timestamp,
        lines=lines,
        total_debits=total_debits,
        total_credits=total_credits,
        total_debit_balance=total_debit_balance,
        total_credit_balance=total_credit_balance,
        is_balanced=is_balanced,
    )


async def get_account_statement(
    conn: asyncpg.Connection, account_id: int
) -> AccountStatementResponse:
    """Genera el extracto de cuenta (libro mayor) con cálculo de saldo acumulado fila a fila."""
    account = await get_account(conn, account_id)
    if not account:
        raise AccountNotFoundError(f"Cuenta {account_id} no encontrada")

    rows = await conn.fetch(
        """
        SELECT p.id AS posting_id, p.transaction_id, p.direction, p.amount,
               t.posted_at, t.description
        FROM postings p
        JOIN transactions t ON t.id = p.transaction_id
        WHERE p.account_id = $1
        ORDER BY t.posted_at ASC, p.id ASC
        """,
        account_id,
    )

    items: list[AccountStatementItem] = []
    running = Decimal("0.0000")
    is_asset_or_expense = account.type in (AccountType.ASSET, AccountType.EXPENSE)

    for r in rows:
        amt = Decimal(str(r["amount"]))
        direction = PostingDirection(r["direction"])
        if is_asset_or_expense:
            running += amt if direction == PostingDirection.DEBIT else -amt
        else:
            running += amt if direction == PostingDirection.CREDIT else -amt

        items.append(
            AccountStatementItem(
                posting_id=r["posting_id"],
                transaction_id=r["transaction_id"],
                posted_at=r["posted_at"],
                description=r["description"],
                direction=direction,
                amount=amt,
                running_balance=running,
            )
        )

    return AccountStatementResponse(
        account=account,
        items=items,
    )

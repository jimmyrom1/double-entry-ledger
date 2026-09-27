import asyncio
from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_concurrent_overdraft_prevention(client: httpx.AsyncClient):
    """Prueba de concurrencia real:

    - Cuenta con saldo inicial de 100.00 EUR y allow_negative = False.
    - 10 peticiones asíncronas simultáneas intentan retirar 30.00 EUR cada una.
    - Demanda total = 300.00 EUR (supera los fondos disponibles).
    - Garantía: exactamente 3 peticiones deben tener éxito (3 * 30 = 90 EUR)
      y 7 deben ser rechazadas (422 Unprocessable Content).
    - El saldo final de la cuenta debe ser estrictamente 10.00 EUR, jamás negativo.
    """
    # 1. Crear cuentas
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja Fuerte", "type": "ASSET", "allow_negative": False},
        )
    ).json()

    gastos = (
        await client.post(
            "/api/accounts",
            json={
                "code": "6000",
                "name": "Gastos Varios",
                "type": "EXPENSE",
                "allow_negative": True,
            },
        )
    ).json()

    capital = (
        await client.post(
            "/api/accounts",
            json={
                "code": "3000",
                "name": "Capital Inicial",
                "type": "EQUITY",
                "allow_negative": True,
            },
        )
    ).json()

    # 2. Depositar saldo inicial de 100.00 EUR en Caja
    init_tx = await client.post(
        "/api/transactions",
        json={
            "idempotency_key": "funding-tx-100",
            "description": "Aportación de fondos",
            "postings": [
                {"account_id": caja["id"], "direction": "DEBIT", "amount": 100.00},
                {"account_id": capital["id"], "direction": "CREDIT", "amount": 100.00},
            ],
        },
    )
    assert init_tx.status_code == 201

    # 3. Lanzar 10 retiradas concurrentes de 30.00 EUR
    async def attempt_withdrawal(idx: int) -> int:
        res = await client.post(
            "/api/transactions",
            json={
                "idempotency_key": f"concurrent-withdraw-{idx}",
                "description": f"Retirada concurrente #{idx}",
                "postings": [
                    {"account_id": gastos["id"], "direction": "DEBIT", "amount": 30.00},
                    {"account_id": caja["id"], "direction": "CREDIT", "amount": 30.00},
                ],
            },
        )
        return res.status_code

    results = await asyncio.gather(*(attempt_withdrawal(i) for i in range(10)))

    success_count = sum(1 for status in results if status == 201)
    insufficient_funds_count = sum(1 for status in results if status == 422)

    # Verificación estricta
    assert success_count == 3, (
        f"Debían triunfar exactamente 3 retiradas, pero triunfaron {success_count}"
    )
    assert insufficient_funds_count == 7, (
        f"Debían fallar exactamente 7 retiradas, pero fallaron {insufficient_funds_count}"
    )

    # Saldo final exacto
    caja_final = (await client.get(f"/api/accounts/{caja['id']}")).json()
    assert Decimal(caja_final["balance"]) == Decimal("10.0000")


@pytest.mark.asyncio
async def test_deadlock_prevention_on_bidirectional_concurrent_transfers(client: httpx.AsyncClient):
    """Prueba anti-deadlock:

    - Múltiples transferencias concurrentes entre Cuenta A y Cuenta B en direcciones cruzadas
      (A -> B y B -> A simultáneamente).
    - Gracias al bloqueo ordenado `ORDER BY id ASC FOR UPDATE`, no ocurre deadlock (código 40P01).
    """
    cta_a = (
        await client.post(
            "/api/accounts",
            json={"code": "1001", "name": "Cuenta A", "type": "ASSET", "allow_negative": True},
        )
    ).json()

    cta_b = (
        await client.post(
            "/api/accounts",
            json={"code": "1002", "name": "Cuenta B", "type": "ASSET", "allow_negative": True},
        )
    ).json()

    async def transfer(idx: int, src_id: int, dst_id: int) -> int:
        res = await client.post(
            "/api/transactions",
            json={
                "idempotency_key": f"cross-transfer-{idx}-{src_id}-{dst_id}",
                "description": f"Transferencia cruzada #{idx}",
                "postings": [
                    {"account_id": dst_id, "direction": "DEBIT", "amount": 10.00},
                    {"account_id": src_id, "direction": "CREDIT", "amount": 10.00},
                ],
            },
        )
        return res.status_code

    # 10 transferencias A -> B y 10 transferencias B -> A ejecutadas concurrentemente
    tasks = []
    for i in range(10):
        tasks.append(transfer(i, cta_a["id"], cta_b["id"]))
        tasks.append(transfer(i + 100, cta_b["id"], cta_a["id"]))

    statuses = await asyncio.gather(*tasks)
    assert all(status == 201 for status in statuses)

    # Ambos saldos netos deben terminar en 0 (100 debitados y 100 acreditados en cada una)
    bal_a = (await client.get(f"/api/accounts/{cta_a['id']}")).json()
    bal_b = (await client.get(f"/api/accounts/{cta_b['id']}")).json()
    assert Decimal(bal_a["balance"]) == Decimal("0.0000")
    assert Decimal(bal_b["balance"]) == Decimal("0.0000")

from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_trial_balance_and_statement(client: httpx.AsyncClient):
    # 1. Crear cuentas de diferentes naturalezas
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET"},
        )
    ).json()

    clientes = (
        await client.post(
            "/api/accounts",
            json={"code": "4300", "name": "Clientes", "type": "ASSET"},
        )
    ).json()

    ventas = (
        await client.post(
            "/api/accounts",
            json={"code": "7000", "name": "Ventas de Mercaderías", "type": "REVENUE"},
        )
    ).json()

    iva = (
        await client.post(
            "/api/accounts",
            json={"code": "4770", "name": "H.P. IVA Repercutido", "type": "LIABILITY"},
        )
    ).json()

    # 2. Registrar venta con factura: Clientes (121) = Ventas (100) + IVA (21)
    tx1 = await client.post(
        "/api/transactions",
        json={
            "idempotency_key": "factura-001",
            "description": "Emisión Factura F-2026-001",
            "postings": [
                {"account_id": clientes["id"], "direction": "DEBIT", "amount": 121.00},
                {"account_id": ventas["id"], "direction": "CREDIT", "amount": 100.00},
                {"account_id": iva["id"], "direction": "CREDIT", "amount": 21.00},
            ],
        },
    )
    assert tx1.status_code == 201

    # 3. Registrar cobro parcial en Caja: Caja (60) = Clientes (60)
    tx2 = await client.post(
        "/api/transactions",
        json={
            "idempotency_key": "cobro-parcial-001",
            "description": "Cobro parcial en efectivo",
            "postings": [
                {"account_id": caja["id"], "direction": "DEBIT", "amount": 60.00},
                {"account_id": clientes["id"], "direction": "CREDIT", "amount": 60.00},
            ],
        },
    )
    assert tx2.status_code == 201

    # 4. Comprobar Balance de Sumas y Saldos (Trial Balance)
    res_tb = await client.get("/api/reports/trial-balance")
    assert res_tb.status_code == 200
    tb = res_tb.json()

    assert tb["is_balanced"] is True
    # Suma total Debe = 121 + 60 = 181.0000
    # Suma total Haber = 100 + 21 + 60 = 181.0000
    assert Decimal(tb["total_debits"]) == Decimal("181.0000")
    assert Decimal(tb["total_credits"]) == Decimal("181.0000")
    assert Decimal(tb["total_debit_balance"]) == Decimal(tb["total_credit_balance"])

    # 5. Comprobar Extracto de la cuenta Clientes (Libro Mayor)
    res_stmt = await client.get(f"/api/accounts/{clientes['id']}/statement")
    assert res_stmt.status_code == 200
    stmt = res_stmt.json()
    assert stmt["account"]["code"] == "4300"
    items = stmt["items"]
    assert len(items) == 2

    # Línea 1: Factura (Debe 121, saldo acumulado 121)
    assert items[0]["direction"] == "DEBIT"
    assert Decimal(items[0]["amount"]) == Decimal("121.0000")
    assert Decimal(items[0]["running_balance"]) == Decimal("121.0000")

    # Línea 2: Cobro (Haber 60, saldo acumulado 61)
    assert items[1]["direction"] == "CREDIT"
    assert Decimal(items[1]["amount"]) == Decimal("60.0000")
    assert Decimal(items[1]["running_balance"]) == Decimal("61.0000")

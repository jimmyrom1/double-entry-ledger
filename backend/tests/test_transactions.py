from decimal import Decimal

import httpx
import pytest


@pytest.mark.asyncio
async def test_create_balanced_transaction(client: httpx.AsyncClient):
    # 1. Crear cuentas
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET", "allow_negative": False},
        )
    ).json()

    ingreso = (
        await client.post(
            "/api/accounts",
            json={"code": "7000", "name": "Ventas", "type": "REVENUE", "allow_negative": True},
        )
    ).json()

    # 2. Registrar transacción balanceada: Debe 100 Caja, Haber 100 Ventas
    tx_res = await client.post(
        "/api/transactions",
        json={
            "idempotency_key": "tx-001",
            "description": "Venta al contado de producto",
            "postings": [
                {"account_id": caja["id"], "direction": "DEBIT", "amount": 100.00},
                {"account_id": ingreso["id"], "direction": "CREDIT", "amount": 100.00},
            ],
        },
    )
    assert tx_res.status_code == 201
    tx_data = tx_res.json()
    assert tx_data["idempotency_key"] == "tx-001"
    assert len(tx_data["postings"]) == 2

    # 3. Comprobar saldos actualizados
    caja_updated = (await client.get(f"/api/accounts/{caja['id']}")).json()
    ingreso_updated = (await client.get(f"/api/accounts/{ingreso['id']}")).json()

    assert Decimal(caja_updated["balance"]) == Decimal("100.0000")
    assert Decimal(ingreso_updated["balance"]) == Decimal("100.0000")


@pytest.mark.asyncio
async def test_reject_unbalanced_transaction(client: httpx.AsyncClient):
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET"},
        )
    ).json()

    ingreso = (
        await client.post(
            "/api/accounts",
            json={"code": "7000", "name": "Ventas", "type": "REVENUE"},
        )
    ).json()

    # Intento de transacción descuadrada: Debe 100 vs Haber 80
    res = await client.post(
        "/api/transactions",
        json={
            "idempotency_key": "tx-unbalanced",
            "description": "Transacción descuadrada",
            "postings": [
                {"account_id": caja["id"], "direction": "DEBIT", "amount": 100.00},
                {"account_id": ingreso["id"], "direction": "CREDIT", "amount": 80.00},
            ],
        },
    )
    assert res.status_code == 422
    assert "descuadrada" in str(res.json()).lower()


@pytest.mark.asyncio
async def test_idempotency_replay(client: httpx.AsyncClient):
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET"},
        )
    ).json()

    ingreso = (
        await client.post(
            "/api/accounts",
            json={"code": "7000", "name": "Ventas", "type": "REVENUE"},
        )
    ).json()

    payload = {
        "idempotency_key": "idemp-test-unique",
        "description": "Pago único con reintento",
        "postings": [
            {"account_id": caja["id"], "direction": "DEBIT", "amount": 50.00},
            {"account_id": ingreso["id"], "direction": "CREDIT", "amount": 50.00},
        ],
    }

    # Primera llamada -> 201 Created
    res1 = await client.post("/api/transactions", json=payload)
    assert res1.status_code == 201
    assert "X-Idempotent-Replay" not in res1.headers
    tx1_id = res1.json()["id"]

    # Segunda llamada idéntica -> 200 OK con header de replay
    res2 = await client.post("/api/transactions", json=payload)
    assert res2.status_code == 200
    assert res2.headers.get("X-Idempotent-Replay") == "true"
    assert res2.json()["id"] == tx1_id

    # Comprobar que no se duplicó el saldo (debe seguir siendo 50, no 100)
    caja_bal = (await client.get(f"/api/accounts/{caja['id']}")).json()
    assert Decimal(caja_bal["balance"]) == Decimal("50.0000")


@pytest.mark.asyncio
async def test_transaction_reversal(client: httpx.AsyncClient):
    caja = (
        await client.post(
            "/api/accounts",
            json={"code": "1000", "name": "Caja", "type": "ASSET", "allow_negative": True},
        )
    ).json()

    banco = (
        await client.post(
            "/api/accounts",
            json={"code": "1010", "name": "Banco", "type": "ASSET", "allow_negative": True},
        )
    ).json()

    # Transacción original: transferencia de Banco a Caja
    tx_orig = (
        await client.post(
            "/api/transactions",
            json={
                "idempotency_key": "tx-orig-transfer",
                "description": "Retirada de efectivo",
                "postings": [
                    {"account_id": caja["id"], "direction": "DEBIT", "amount": 250.00},
                    {"account_id": banco["id"], "direction": "CREDIT", "amount": 250.00},
                ],
            },
        )
    ).json()

    # Revertir transacción
    rev_res = await client.post(
        f"/api/transactions/{tx_orig['id']}/reversal",
        json={"idempotency_key": "rev-key-01", "reason": "Error en importe ingresado"},
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()
    assert rev_data["reversal_of_id"] == tx_orig["id"]

    # Comprobar que los saldos han vuelto a 0
    caja_bal = (await client.get(f"/api/accounts/{caja['id']}")).json()
    banco_bal = (await client.get(f"/api/accounts/{banco['id']}")).json()
    assert Decimal(caja_bal["balance"]) == Decimal("0.0000")
    assert Decimal(banco_bal["balance"]) == Decimal("0.0000")

    # Intentar revertir por segunda vez debe fallar con 409
    dup_rev = await client.post(
        f"/api/transactions/{tx_orig['id']}/reversal",
        json={"idempotency_key": "rev-key-02"},
    )
    assert dup_rev.status_code == 409


@pytest.mark.asyncio
async def test_list_and_get_transaction(client: httpx.AsyncClient):
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
                "idempotency_key": "tx-list-test",
                "description": "Prueba de listado",
                "postings": [
                    {"account_id": caja["id"], "direction": "DEBIT", "amount": 15.00},
                    {"account_id": ventas["id"], "direction": "CREDIT", "amount": 15.00},
                ],
            },
        )
    ).json()

    # Listar transacciones
    res_list = await client.get("/api/transactions")
    assert res_list.status_code == 200
    txs = res_list.json()
    assert len(txs) == 1
    assert txs[0]["id"] == tx["id"]

    # Detalle de transacción
    res_detail = await client.get(f"/api/transactions/{tx['id']}")
    assert res_detail.status_code == 200
    assert res_detail.json()["description"] == "Prueba de listado"

    # Transacción inexistente
    res_404 = await client.get("/api/transactions/999999")
    assert res_404.status_code == 404

    # Reversión de transacción inexistente
    res_rev_404 = await client.post(
        "/api/transactions/999999/reversal",
        json={"idempotency_key": "rev-nonexistent"},
    )
    assert res_rev_404.status_code == 404

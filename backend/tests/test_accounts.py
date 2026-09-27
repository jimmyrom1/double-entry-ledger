import httpx
import pytest


@pytest.mark.asyncio
async def test_create_and_list_accounts(client: httpx.AsyncClient):
    # Crear cuenta de Activo (Caja)
    res_asset = await client.post(
        "/api/accounts",
        json={
            "code": "1000",
            "name": "Caja y Bancos",
            "type": "ASSET",
            "currency": "EUR",
            "allow_negative": False,
        },
    )
    assert res_asset.status_code == 201
    data_asset = res_asset.json()
    assert data_asset["code"] == "1000"
    assert data_asset["type"] == "ASSET"
    assert data_asset["allow_negative"] is False
    assert float(data_asset["balance"]) == 0.0

    # Crear cuenta de Ingresos
    res_rev = await client.post(
        "/api/accounts",
        json={
            "code": "7000",
            "name": "Ventas de Servicios",
            "type": "REVENUE",
            "currency": "eur",  # Validador debe pasar a EUR mayúsculas
            "allow_negative": True,
        },
    )
    assert res_rev.status_code == 201
    assert res_rev.json()["currency"] == "EUR"

    # Intentar duplicar código de cuenta
    res_dup = await client.post(
        "/api/accounts",
        json={
            "code": "1000",
            "name": "Caja Duplicada",
            "type": "ASSET",
        },
    )
    assert res_dup.status_code == 409
    assert "Ya existe una cuenta con el código '1000'" in res_dup.json()["detail"]

    # Listar cuentas
    res_list = await client.get("/api/accounts")
    assert res_list.status_code == 200
    accounts = res_list.json()
    assert len(accounts) == 2
    assert accounts[0]["code"] == "1000"
    assert accounts[1]["code"] == "7000"


@pytest.mark.asyncio
async def test_get_account_detail_and_not_found(client: httpx.AsyncClient):
    res_create = await client.post(
        "/api/accounts",
        json={
            "code": "5700",
            "name": "Caja Chica",
            "type": "ASSET",
        },
    )
    assert res_create.status_code == 201
    acc_id = res_create.json()["id"]

    res_get = await client.get(f"/api/accounts/{acc_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == acc_id

    res_404 = await client.get("/api/accounts/99999")
    assert res_404.status_code == 404

    res_stmt_404 = await client.get("/api/accounts/99999/statement")
    assert res_stmt_404.status_code == 404


@pytest.mark.asyncio
async def test_health_check(client: httpx.AsyncClient):
    res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "double-entry-ledger"}

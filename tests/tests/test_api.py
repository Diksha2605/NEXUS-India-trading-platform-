# ============================================================
#  NXIO — tests/test_api.py
#  API Auth + Error Path Tests
# ============================================================
import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["NXIO_DB_PATH"] = "data/test_nxio.db"

from fastapi.testclient import TestClient
from paper_trading.database import db_reset

# Import app after env is set
from api.server import app
from api.settings import settings

client = TestClient(app, raise_server_exceptions=False)
VALID_KEY = settings.nxio_api_key


@pytest.fixture(autouse=True)
def fresh_db():
    db_reset()
    yield
    db_reset()


# ── Test 2.6a — Auth required on /paper/buy ───────────────
def test_buy_requires_auth():
    response = client.post("/paper/buy", json={
        "symbol": "RELIANCE", "price": 2500.0, "quantity": 1
    })
    assert response.status_code == 403, (
        f"Expected 403 without API key, got {response.status_code}"
    )


# ── Test 2.6b — Auth required on /paper/sell ──────────────
def test_sell_requires_auth():
    response = client.post("/paper/sell", json={
        "symbol": "RELIANCE", "price": 2500.0, "quantity": 1
    })
    assert response.status_code == 403


# ── Test 2.6c — Auth required on /paper/reset ─────────────
def test_reset_requires_auth():
    response = client.post("/paper/reset")
    assert response.status_code == 403


# ── Test 2.6d — Valid API key is accepted ─────────────────
def test_buy_with_valid_key_succeeds():
    response = client.post(
        "/paper/buy",
        json={"symbol": "RELIANCE", "price": 2500.0, "quantity": 1},
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True


# ── Test 2.6e — Wrong API key is rejected ─────────────────
def test_buy_with_wrong_key_rejected():
    response = client.post(
        "/paper/buy",
        json={"symbol": "RELIANCE", "price": 2500.0, "quantity": 1},
        headers={"X-API-Key": "wrong-key-000"},
    )
    assert response.status_code == 403


# ── Test: /health is public (no auth needed) ──────────────
def test_health_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["system"] == "NXIO"


# ── Test: /paper/portfolio is public ──────────────────────
def test_portfolio_is_public():
    response = client.get("/paper/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert "cash" in data


# ── Test: Invalid price rejected (validation) ─────────────
def test_buy_negative_price_rejected():
    response = client.post(
        "/paper/buy",
        json={"symbol": "RELIANCE", "price": -100.0, "quantity": 1},
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 422   # Pydantic validation error


# ── Test: Zero quantity rejected ──────────────────────────
def test_buy_zero_quantity_rejected():
    response = client.post(
        "/paper/buy",
        json={"symbol": "RELIANCE", "price": 2500.0, "quantity": 0},
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 422


# ── Test: SL above price rejected ─────────────────────────
def test_buy_sl_above_price_rejected():
    response = client.post(
        "/paper/buy",
        json={"symbol": "RELIANCE", "price": 2500.0, "quantity": 1, "sl": 3000.0},
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 422


# ── Test: Sell non-existent symbol returns error ──────────
def test_sell_symbol_not_in_holdings():
    response = client.post(
        "/paper/sell",
        json={"symbol": "FAKESYMBOL", "price": 100.0, "quantity": 1},
        headers={"X-API-Key": VALID_KEY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "not in holdings" in data["error"]
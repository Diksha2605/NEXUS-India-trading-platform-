# ============================================================
#  NXIO — tests/test_portfolio.py
#  Order Math + Portfolio Logic Tests
# ============================================================
import pytest
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use a separate test DB — never touch production data
os.environ["NXIO_DB_PATH"] = "data/test_nxio.db"

from paper_trading.database import init_db, db_reset, DB_PATH
from paper_trading.portfolio import (
    buy_stock, sell_stock, get_portfolio_summary, reset_portfolio
)

STARTING_CAPITAL = 100_000.0


@pytest.fixture(autouse=True)
def fresh_portfolio():
    """Reset DB before every single test — guaranteed clean slate."""
    db_reset()
    yield
    db_reset()


# ── Test 2.3 — BUY deducts correct cash ───────────────────
def test_buy_deducts_correct_cash():
    result = buy_stock("RELIANCE", price=2500.0, quantity=10)
    assert result["success"] is True

    summary = get_portfolio_summary()
    expected_cash = STARTING_CAPITAL - (2500.0 * 10)
    assert summary["cash"] == expected_cash, (
        f"Expected cash Rs.{expected_cash}, got Rs.{summary['cash']}"
    )


# ── Test 2.4 — Insufficient funds rejected ────────────────
def test_insufficient_funds_rejected():
    # Try to buy more than we have (Rs.1,00,000 capital)
    result = buy_stock("TCS", price=4000.0, quantity=100)  # Rs.4,00,000 needed
    assert result["success"] is False
    assert "Insufficient funds" in result["error"]

    # Cash should be unchanged
    summary = get_portfolio_summary()
    assert summary["cash"] == STARTING_CAPITAL


# ── Test 2.5 — Partial sell leaves correct quantity ───────
def test_partial_sell_correct_quantity():
    # Buy 20 shares
    buy_stock("INFY", price=1500.0, quantity=20)

    # Sell only 8
    result = sell_stock("INFY", price=1600.0, quantity=8)
    assert result["success"] is True

    # 12 shares should remain
    summary = get_portfolio_summary()
    holding = next((h for h in summary["holdings"] if h["symbol"] == "INFY"), None)
    assert holding is not None, "INFY should still be in holdings"
    assert holding["quantity"] == 12, (
        f"Expected 12 shares remaining, got {holding['quantity']}"
    )


# ── Bonus: Sell more than held is rejected ─────────────────
def test_sell_more_than_held_rejected():
    buy_stock("WIPRO", price=500.0, quantity=10)
    result = sell_stock("WIPRO", price=550.0, quantity=50)
    assert result["success"] is False
    assert "available" in result["error"]


# ── Bonus: PnL calculated correctly ───────────────────────
def test_sell_pnl_correct():
    buy_stock("HDFC", price=1000.0, quantity=5)
    result = sell_stock("HDFC", price=1200.0, quantity=5)

    assert result["success"] is True
    assert result["pnl"] == round((1200.0 - 1000.0) * 5, 2)   # Rs.1000
    assert result["pnl_pct"] == 20.0


# ── Bonus: Averaging into existing position ───────────────
def test_buy_averages_existing_position():
    buy_stock("SBIN", price=600.0, quantity=10)   # avg = 600
    buy_stock("SBIN", price=400.0, quantity=10)   # avg should be 500

    summary = get_portfolio_summary()
    holding = next(h for h in summary["holdings"] if h["symbol"] == "SBIN")
    assert holding["quantity"] == 20
    assert holding["avg_price"] == 500.0


# ── Bonus: Full sell removes from holdings ─────────────────
def test_full_sell_removes_holding():
    buy_stock("TATAMOTORS", price=800.0, quantity=5)
    sell_stock("TATAMOTORS", price=850.0, quantity=5)

    summary = get_portfolio_summary()
    symbols = [h["symbol"] for h in summary["holdings"]]
    assert "TATAMOTORS" not in symbols


# ── Bonus: Idempotency key prevents duplicate order ───────
def test_idempotency_key_prevents_duplicate():
    key = "test-idem-001"
    r1 = buy_stock("MARUTI", price=10000.0, quantity=1, idempotency_key=key)
    r2 = buy_stock("MARUTI", price=10000.0, quantity=1, idempotency_key=key)

    assert r1["success"] is True
    assert r2.get("duplicate") is True

    # Only 1 deduction should have happened
    summary = get_portfolio_summary()
    assert summary["cash"] == STARTING_CAPITAL - 10000.0
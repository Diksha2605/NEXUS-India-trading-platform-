# ============================================================
#  NXIO — paper_trading/portfolio.py
#  Virtual Paper Trading Engine — SQLite Backend
#  Starting Capital: Rs.1,00,000
# ============================================================
import os, sys
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from paper_trading.database import (
    init_db,
    db_load_portfolio, db_save_portfolio,
    db_load_holdings, db_upsert_holding, db_delete_holding,
    db_load_orders, db_insert_order, db_idempotency_check,
    db_load_history, db_insert_history,
    db_reset,
    STARTING_CAPITAL,
)

# Init DB schema on import (safe — only creates tables if missing)
init_db()


def log(msg, level="INFO"):
    colors = {"INFO": Fore.CYAN, "OK": Fore.GREEN, "WARN": Fore.YELLOW, "ERR": Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level, Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")


# ── Public helpers (server.py uses these directly) ────────
def load_orders() -> list:
    return db_load_orders()


def load_history() -> list:
    return db_load_history()


# ── Core Trading Functions ────────────────────────────────
def buy_stock(symbol, price, quantity, signal_conf=None, sl=None, tp=None,
              idempotency_key=None):
    """
    Place a paper BUY order.
    Returns: dict with result
    """
    # Idempotency check — return existing order if key already used
    if idempotency_key:
        existing = db_idempotency_check(idempotency_key)
        if existing:
            log(f"Duplicate BUY ignored (idempotency_key={idempotency_key})", "WARN")
            return {"success": True, "duplicate": True, "order": existing}

    portfolio = db_load_portfolio()
    holdings  = db_load_holdings()

    total_cost = round(price * quantity, 2)

    # Check funds
    if total_cost > portfolio["cash"]:
        return {
            "success": False,
            "error":   f"Insufficient funds. Need Rs.{total_cost}, have Rs.{portfolio['cash']}",
        }

    # Deduct cash
    new_cash = round(portfolio["cash"] - total_cost, 2)

    # Update holdings (average-in if already holding)
    if symbol in holdings:
        existing_h  = holdings[symbol]
        total_qty   = existing_h["quantity"] + quantity
        avg_price   = round(
            (existing_h["avg_price"] * existing_h["quantity"] + price * quantity) / total_qty, 2
        )
        invested    = round(avg_price * total_qty, 2)
        final_sl    = sl or existing_h.get("sl")
        final_tp    = tp or existing_h.get("tp")
    else:
        total_qty = quantity
        avg_price = price
        invested  = total_cost
        final_sl  = sl
        final_tp  = tp

    db_upsert_holding(symbol, total_qty, avg_price, invested, final_sl, final_tp)
    db_save_portfolio(
        cash           = new_cash,
        total_trades   = portfolio["total_trades"] + 1,
        winning_trades = portfolio["winning_trades"],
        losing_trades  = portfolio["losing_trades"],
    )

    ts    = datetime.now().strftime("%d %b %Y %H:%M:%S")
    order_id = db_insert_order(
        type_="BUY", symbol=symbol, price=price, quantity=quantity,
        total=total_cost, sl=sl, tp=tp, confidence=signal_conf,
        pnl=None, pnl_pct=None, status="EXECUTED",
        idempotency_key=idempotency_key, timestamp=ts,
    )

    log(f"BUY {symbol} | Qty:{quantity} | Price:Rs.{price} | Total:Rs.{total_cost}", "OK")

    order = {
        "id": order_id, "type": "BUY", "symbol": symbol,
        "price": price, "quantity": quantity, "total": total_cost,
        "sl": sl, "tp": tp, "confidence": signal_conf,
        "status": "EXECUTED", "timestamp": ts,
    }
    return {"success": True, "order": order, "cash_remaining": new_cash}


def sell_stock(symbol, price, quantity):
    """
    Place a paper SELL order.
    Returns: dict with result
    """
    portfolio = db_load_portfolio()
    holdings  = db_load_holdings()

    if symbol not in holdings:
        return {"success": False, "error": f"{symbol} not in holdings"}

    holding = holdings[symbol]
    if quantity > holding["quantity"]:
        return {
            "success": False,
            "error":   f"Only {holding['quantity']} shares available, can't sell {quantity}",
        }

    avg_price   = holding["avg_price"]
    total_value = round(price * quantity, 2)
    pnl         = round((price - avg_price) * quantity, 2)
    pnl_pct     = round((price - avg_price) / avg_price * 100, 2)

    # Update cash
    new_cash = round(portfolio["cash"] + total_value, 2)

    # Update or remove holding
    remaining_qty = holding["quantity"] - quantity
    if remaining_qty == 0:
        db_delete_holding(symbol)
    else:
        new_invested = round(avg_price * remaining_qty, 2)
        db_upsert_holding(symbol, remaining_qty, avg_price, new_invested,
                          holding.get("sl"), holding.get("tp"))

    # Track wins / losses
    won = pnl >= 0
    db_save_portfolio(
        cash           = new_cash,
        total_trades   = portfolio["total_trades"],
        winning_trades = portfolio["winning_trades"] + (1 if won else 0),
        losing_trades  = portfolio["losing_trades"]  + (0 if won else 1),
    )

    ts = datetime.now().strftime("%d %b %Y %H:%M:%S")

    db_insert_history(
        symbol=symbol, buy_price=avg_price, sell_price=price,
        quantity=quantity, pnl=pnl, pnl_pct=pnl_pct,
        result="WIN" if won else "LOSS", timestamp=ts,
    )

    order_id = db_insert_order(
        type_="SELL", symbol=symbol, price=price, quantity=quantity,
        total=total_value, sl=None, tp=None, confidence=None,
        pnl=pnl, pnl_pct=pnl_pct, status="EXECUTED",
        idempotency_key=None, timestamp=ts,
    )

    log(f"SELL {symbol} | Qty:{quantity} | Price:Rs.{price} | P&L:Rs.{pnl} ({pnl_pct}%)", "OK")

    order = {
        "id": order_id, "type": "SELL", "symbol": symbol,
        "price": price, "quantity": quantity, "total": total_value,
        "pnl": pnl, "pnl_pct": pnl_pct,
        "status": "EXECUTED", "timestamp": ts,
    }
    return {"success": True, "order": order, "pnl": pnl, "pnl_pct": pnl_pct}


def get_portfolio_summary(current_prices=None):
    """Get full portfolio summary with live P&L."""
    portfolio = db_load_portfolio()
    holdings  = db_load_holdings()
    history   = db_load_history()

    holdings_value  = 0
    holdings_detail = []

    for symbol, holding in holdings.items():
        qty       = holding["quantity"]
        avg_price = holding["avg_price"]
        invested  = holding["invested"]

        curr_price = avg_price
        if current_prices and symbol in current_prices:
            curr_price = current_prices[symbol]

        curr_value     = round(curr_price * qty, 2)
        unrealized     = round(curr_value - invested, 2)
        unrealized_pct = round((unrealized / invested) * 100, 2) if invested else 0
        holdings_value += curr_value

        holdings_detail.append({
            "symbol":         symbol,
            "quantity":       qty,
            "avg_price":      avg_price,
            "current_price":  curr_price,
            "invested":       invested,
            "current_value":  curr_value,
            "unrealized_pnl": unrealized,
            "unrealized_pct": unrealized_pct,
            "sl":             holding.get("sl"),
            "tp":             holding.get("tp"),
        })

    total_value     = round(portfolio["cash"] + holdings_value, 2)
    overall_pnl     = round(total_value - STARTING_CAPITAL, 2)
    overall_pnl_pct = round((overall_pnl / STARTING_CAPITAL) * 100, 2)
    realized_pnl    = sum(t["pnl"] for t in history)

    total_closed = portfolio["winning_trades"] + portfolio["losing_trades"]
    win_rate = round(portfolio["winning_trades"] / total_closed * 100, 1) if total_closed else 0

    return {
        "cash":             portfolio["cash"],
        "starting_capital": STARTING_CAPITAL,
        "holdings_value":   round(holdings_value, 2),
        "total_value":      total_value,
        "overall_pnl":      overall_pnl,
        "overall_pnl_pct":  overall_pnl_pct,
        "realized_pnl":     round(realized_pnl, 2),
        "unrealized_pnl":   round(
            holdings_value - sum(h["invested"] for h in holdings_detail), 2
        ),
        "holdings":         holdings_detail,
        "total_trades":     portfolio["total_trades"],
        "winning_trades":   portfolio["winning_trades"],
        "losing_trades":    portfolio["losing_trades"],
        "win_rate":         win_rate,
        "created":          portfolio.get("created", ""),
    }


def reset_portfolio():
    """Reset portfolio to starting state."""
    db_reset()
    log("Portfolio reset to Rs.1,00,000", "OK")
    return {"success": True, "message": "Portfolio reset", "cash": STARTING_CAPITAL}
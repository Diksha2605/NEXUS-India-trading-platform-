# ============================================================
#  NEXUS INDIA — paper_trading/portfolio.py
#  Virtual Paper Trading Engine
#  Starting Capital: Rs.1,00,000
# ============================================================
import os, sys, json
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# ── Storage ───────────────────────────────────────────────
DATA_DIR  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PORT_FILE = os.path.join(DATA_DIR, "portfolio.json")
ORD_FILE  = os.path.join(DATA_DIR, "orders.json")
HIST_FILE = os.path.join(DATA_DIR, "trade_history.json")
STARTING_CAPITAL = 100000  # Rs.1,00,000
def log(msg, level="INFO"):
    colors = {"INFO":Fore.CYAN,"OK":Fore.GREEN,"WARN":Fore.YELLOW,"ERR":Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level,Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
# ── Load / Save ───────────────────────────────────────────
def load_portfolio():
    if os.path.exists(PORT_FILE):
        with open(PORT_FILE, "r") as f:
            return json.load(f)
    return {
        "cash":          STARTING_CAPITAL,
        "starting":      STARTING_CAPITAL,
        "holdings":      {},
        "created":       datetime.now().strftime("%d %b %Y"),
        "total_trades":  0,
        "winning_trades":0,
        "losing_trades": 0,
    }
def save_portfolio(portfolio):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PORT_FILE, "w") as f:
        json.dump(portfolio, f, indent=2)
def load_orders():
    if os.path.exists(ORD_FILE):
        with open(ORD_FILE, "r") as f:
            return json.load(f)
    return []
def save_orders(orders):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(ORD_FILE, "w") as f:
        json.dump(orders, f, indent=2)
def load_history():
    if os.path.exists(HIST_FILE):
        with open(HIST_FILE, "r") as f:
            return json.load(f)
    return []
def save_history(history):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(HIST_FILE, "w") as f:
        json.dump(history, f, indent=2)
# ── Core Trading Functions ────────────────────────────────
def buy_stock(symbol, price, quantity, signal_conf=None, sl=None, tp=None):
    """
    Place a paper BUY order.
    Returns: dict with result
    """
    portfolio = load_portfolio()
    orders    = load_orders()
    total_cost = round(price * quantity, 2)
    # Check funds
    if total_cost > portfolio["cash"]:
        return {
            "success": False,
            "error":   f"Insufficient funds. Need Rs.{total_cost}, have Rs.{portfolio['cash']}",
        }
    # Deduct cash
    portfolio["cash"] = round(portfolio["cash"] - total_cost, 2)
    # Add to holdings
    if symbol in portfolio["holdings"]:
        # Average out existing position
        existing = portfolio["holdings"][symbol]
        total_qty = existing["quantity"] + quantity
        avg_price = round(
            (existing["avg_price"] * existing["quantity"] + price * quantity) / total_qty, 2
        )
        portfolio["holdings"][symbol] = {
            "quantity":  total_qty,
            "avg_price": avg_price,
            "invested":  round(avg_price * total_qty, 2),
            "sl":        sl or existing.get("sl"),
            "tp":        tp or existing.get("tp"),
        }
    else:
        portfolio["holdings"][symbol] = {
            "quantity":  quantity,
            "avg_price": price,
            "invested":  total_cost,
            "sl":        sl,
            "tp":        tp,
        }
    portfolio["total_trades"] += 1
    # Save order
    order = {
        "id":          len(orders) + 1,
        "type":        "BUY",
        "symbol":      symbol,
        "price":       price,
        "quantity":    quantity,
        "total":       total_cost,
        "sl":          sl,
        "tp":          tp,
        "confidence":  signal_conf,
        "status":      "EXECUTED",
        "timestamp":   datetime.now().strftime("%d %b %Y %H:%M:%S"),
    }
    orders.append(order)
    save_portfolio(portfolio)
    save_orders(orders)
    log(f"BUY {symbol} | Qty:{quantity} | Price:Rs.{price} | Total:Rs.{total_cost}", "OK")
    return {"success": True, "order": order, "portfolio": portfolio}
def sell_stock(symbol, price, quantity):
    """
    Place a paper SELL order.
    Returns: dict with result
    """
    portfolio = load_portfolio()
    orders    = load_orders()
    history   = load_history()
    if symbol not in portfolio["holdings"]:
        return {"success": False, "error": f"{symbol} not in holdings"}
    holding = portfolio["holdings"][symbol]
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
    portfolio["cash"] = round(portfolio["cash"] + total_value, 2)
    # Update holdings
    if quantity == holding["quantity"]:
        del portfolio["holdings"][symbol]
    else:
        portfolio["holdings"][symbol]["quantity"] -= quantity
        portfolio["holdings"][symbol]["invested"]  = round(
            portfolio["holdings"][symbol]["avg_price"] *
            portfolio["holdings"][symbol]["quantity"], 2
        )
    # Track wins/losses
    if pnl >= 0:
        portfolio["winning_trades"] += 1
    else:
        portfolio["losing_trades"] += 1
    # Save to history
    trade = {
        "type":      "SELL",
        "symbol":    symbol,
        "buy_price": avg_price,
        "sell_price":price,
        "quantity":  quantity,
        "pnl":       pnl,
        "pnl_pct":   pnl_pct,
        "result":    "WIN" if pnl >= 0 else "LOSS",
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M:%S"),
    }
    history.append(trade)
    order = {
        "id":        len(orders) + 1,
        "type":      "SELL",
        "symbol":    symbol,
        "price":     price,
        "quantity":  quantity,
        "total":     total_value,
        "pnl":       pnl,
        "pnl_pct":   pnl_pct,
        "status":    "EXECUTED",
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M:%S"),
    }
    orders.append(order)
    save_portfolio(portfolio)
    save_orders(orders)
    save_history(history)
    log(f"SELL {symbol} | Qty:{quantity} | Price:Rs.{price} | P&L:Rs.{pnl} ({pnl_pct}%)", "OK")
    return {"success": True, "order": order, "pnl": pnl, "pnl_pct": pnl_pct}
def get_portfolio_summary(current_prices=None):
    """
    Get full portfolio summary with live P&L.
    current_prices: dict of {symbol: price}
    """
    portfolio = load_portfolio()
    history   = load_history()
    holdings_value = 0
    holdings_detail = []
    for symbol, holding in portfolio["holdings"].items():
        qty       = holding["quantity"]
        avg_price = holding["avg_price"]
        invested  = holding["invested"]
        # Use current price if available
        curr_price = avg_price
        if current_prices and symbol in current_prices:
            curr_price = current_prices[symbol]
        curr_value  = round(curr_price * qty, 2)
        unrealized  = round(curr_value - invested, 2)
        unrealized_pct = round((unrealized / invested) * 100, 2) if invested else 0
        holdings_value += curr_value
        holdings_detail.append({
            "symbol":          symbol,
            "quantity":        qty,
            "avg_price":       avg_price,
            "current_price":   curr_price,
            "invested":        invested,
            "current_value":   curr_value,
            "unrealized_pnl":  unrealized,
            "unrealized_pct":  unrealized_pct,
            "sl":              holding.get("sl"),
            "tp":              holding.get("tp"),
        })
    total_value    = round(portfolio["cash"] + holdings_value, 2)
    total_invested = STARTING_CAPITAL
    overall_pnl    = round(total_value - total_invested, 2)
    overall_pnl_pct= round((overall_pnl / total_invested) * 100, 2)
    # Realized P&L from history
    realized_pnl = sum(t["pnl"] for t in history)
    # Win rate
    total_closed = portfolio["winning_trades"] + portfolio["losing_trades"]
    win_rate = round(portfolio["winning_trades"] / total_closed * 100, 1) if total_closed > 0 else 0
    return {
        "cash":              portfolio["cash"],
        "starting_capital":  STARTING_CAPITAL,
        "holdings_value":    round(holdings_value, 2),
        "total_value":       total_value,
        "overall_pnl":       overall_pnl,
        "overall_pnl_pct":   overall_pnl_pct,
        "realized_pnl":      round(realized_pnl, 2),
        "unrealized_pnl":    round(holdings_value - sum(h["invested"] for h in holdings_detail), 2),
        "holdings":          holdings_detail,
        "total_trades":      portfolio["total_trades"],
        "winning_trades":    portfolio["winning_trades"],
        "losing_trades":     portfolio["losing_trades"],
        "win_rate":          win_rate,
        "created":           portfolio.get("created", ""),
    }
def reset_portfolio():
    """Reset portfolio to starting state."""
    if os.path.exists(PORT_FILE): os.remove(PORT_FILE)
    if os.path.exists(ORD_FILE):  os.remove(ORD_FILE)
    if os.path.exists(HIST_FILE): os.remove(HIST_FILE)
    log("Portfolio reset to Rs.1,00,000", "OK")
    return {"success": True, "message": "Portfolio reset", "cash": STARTING_CAPITAL}

# ============================================================
#  NXIO — paper_trading/database.py
#  SQLite Data Layer — Atomic Transactions, Crash-Safe
# ============================================================
import os
import sqlite3
from datetime import datetime
from contextlib import contextmanager

# ── DB Path ───────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH  = os.path.join(DATA_DIR, "nxio.db")

STARTING_CAPITAL = 100_000.0


@contextmanager
def get_conn():
    """Context manager — always commits or rolls back atomically."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # crash-safe writes
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema Init ───────────────────────────────────────────
def init_db():
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS portfolio (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                cash            REAL    NOT NULL DEFAULT 100000.0,
                starting        REAL    NOT NULL DEFAULT 100000.0,
                total_trades    INTEGER NOT NULL DEFAULT 0,
                winning_trades  INTEGER NOT NULL DEFAULT 0,
                losing_trades   INTEGER NOT NULL DEFAULT 0,
                created         TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS holdings (
                symbol      TEXT    PRIMARY KEY,
                quantity    INTEGER NOT NULL,
                avg_price   REAL    NOT NULL,
                invested    REAL    NOT NULL,
                sl          REAL,
                tp          REAL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                type            TEXT    NOT NULL,
                symbol          TEXT    NOT NULL,
                price           REAL    NOT NULL,
                quantity        INTEGER NOT NULL,
                total           REAL    NOT NULL,
                sl              REAL,
                tp              REAL,
                confidence      REAL,
                pnl             REAL,
                pnl_pct         REAL,
                status          TEXT    NOT NULL DEFAULT 'EXECUTED',
                idempotency_key TEXT    UNIQUE,
                timestamp       TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS trade_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                type        TEXT    NOT NULL DEFAULT 'SELL',
                symbol      TEXT    NOT NULL,
                buy_price   REAL    NOT NULL,
                sell_price  REAL    NOT NULL,
                quantity    INTEGER NOT NULL,
                pnl         REAL    NOT NULL,
                pnl_pct     REAL    NOT NULL,
                result      TEXT    NOT NULL,
                timestamp   TEXT    NOT NULL
            );
        """)

        # Seed portfolio row if empty (only once)
        row = conn.execute("SELECT id FROM portfolio WHERE id = 1").fetchone()
        if not row:
            conn.execute(
                "INSERT INTO portfolio (id, cash, starting, created) VALUES (1, ?, ?, ?)",
                (STARTING_CAPITAL, STARTING_CAPITAL, datetime.now().strftime("%d %b %Y"))
            )


# ── Portfolio ─────────────────────────────────────────────
def db_load_portfolio() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM portfolio WHERE id = 1").fetchone()
        if not row:
            return {}
        return dict(row)


def db_save_portfolio(cash: float, total_trades: int, winning_trades: int, losing_trades: int):
    with get_conn() as conn:
        conn.execute("""
            UPDATE portfolio
            SET cash=?, total_trades=?, winning_trades=?, losing_trades=?
            WHERE id=1
        """, (cash, total_trades, winning_trades, losing_trades))


# ── Holdings ──────────────────────────────────────────────
def db_load_holdings() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM holdings").fetchall()
        return {r["symbol"]: dict(r) for r in rows}


def db_upsert_holding(symbol, quantity, avg_price, invested, sl, tp):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO holdings (symbol, quantity, avg_price, invested, sl, tp)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                quantity=excluded.quantity,
                avg_price=excluded.avg_price,
                invested=excluded.invested,
                sl=excluded.sl,
                tp=excluded.tp
        """, (symbol, quantity, avg_price, invested, sl, tp))


def db_delete_holding(symbol: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM holdings WHERE symbol = ?", (symbol,))


# ── Orders ────────────────────────────────────────────────
def db_load_orders() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def db_insert_order(type_, symbol, price, quantity, total, sl, tp,
                    confidence, pnl, pnl_pct, status, idempotency_key, timestamp) -> int:
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO orders
                (type, symbol, price, quantity, total, sl, tp,
                 confidence, pnl, pnl_pct, status, idempotency_key, timestamp)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (type_, symbol, price, quantity, total, sl, tp,
              confidence, pnl, pnl_pct, status, idempotency_key, timestamp))
        return cur.lastrowid


def db_idempotency_check(key: str) -> dict | None:
    """Return existing order if idempotency_key already used."""
    if not key:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return dict(row) if row else None


# ── Trade History ─────────────────────────────────────────
def db_load_history() -> list:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM trade_history ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def db_insert_history(symbol, buy_price, sell_price, quantity, pnl, pnl_pct, result, timestamp):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO trade_history
                (symbol, buy_price, sell_price, quantity, pnl, pnl_pct, result, timestamp)
            VALUES (?,?,?,?,?,?,?,?)
        """, (symbol, buy_price, sell_price, quantity, pnl, pnl_pct, result, timestamp))


# ── Reset ─────────────────────────────────────────────────
def db_reset():
    """Wipe all data and re-seed starting capital."""
    with get_conn() as conn:
        conn.executescript("""
            DELETE FROM trade_history;
            DELETE FROM orders;
            DELETE FROM holdings;
            DELETE FROM portfolio;
        """)
        conn.execute(
            "INSERT INTO portfolio (id, cash, starting, created) VALUES (1, ?, ?, ?)",
            (STARTING_CAPITAL, STARTING_CAPITAL, datetime.now().strftime("%d %b %Y"))
        )
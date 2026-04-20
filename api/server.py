# ============================================================
#  NXIO — api/server.py
#  FastAPI Backend — Secured + Validated + Monitored
# ============================================================
import os, sys, shutil, logging
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import NSE_SYMBOLS, TIMEFRAMES, MIN_CONFIDENCE, PROC_DIR
from signals.generator import generate_signal, scan_all
from brain.predictor import predict_next_candles
from paper_trading.portfolio import (
    buy_stock, sell_stock, get_portfolio_summary,
    load_orders, load_history, reset_portfolio
)
from paper_trading.database import DB_PATH
from api.settings import settings
from api.auth import verify_api_key
from api.logging_config import setup_logging, RequestIDMiddleware

# ── Logging setup ─────────────────────────────────────────
setup_logging(settings.log_level)
logger = logging.getLogger("nxio.server")

app = FastAPI(title="NXIO API", version="3.0.0")

# ── Middlewares ───────────────────────────────────────────
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.allowed_origin],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)


def require_paper_mode():
    if settings.nxio_env not in ("paper", "development"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=403,
            detail="Real trading not enabled. Set NXIO_ENV=paper in .env"
        )


# ── Request Models ────────────────────────────────────────
class BuyRequest(BaseModel):
    symbol:          str          = Field(..., min_length=1, max_length=20)
    price:           float        = Field(..., gt=0, le=1_000_000)
    quantity:        int          = Field(..., gt=0, le=10_000)
    sl:              float | None = Field(None, gt=0)
    tp:              float | None = Field(None, gt=0)
    confidence:      float | None = Field(None, ge=0, le=100)
    idempotency_key: str   | None = None

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v):
        return v.upper().strip()

    @model_validator(mode="after")
    def sl_below_price(self):
        if self.sl is not None and self.sl >= self.price:
            raise ValueError("Stop loss must be below entry price for BUY")
        return self


class SellRequest(BaseModel):
    symbol:   str   = Field(..., min_length=1, max_length=20)
    price:    float = Field(..., gt=0, le=1_000_000)
    quantity: int   = Field(..., gt=0, le=10_000)

    @field_validator("symbol")
    @classmethod
    def symbol_uppercase(cls, v):
        return v.upper().strip()


# ── Enhanced Health Check ─────────────────────────────────
@app.get("/health")
def health():
    checks = {}

    # DB check
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Model files check
    models_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "brain", "models"
    )
    model_files = []
    if os.path.exists(models_dir):
        model_files = [f for f in os.listdir(models_dir) if f.endswith(".keras") or f.endswith(".h5")]
    checks["models"] = f"{len(model_files)} loaded" if model_files else "no models found"

    # Disk space check
    try:
        usage    = shutil.disk_usage("/")
        free_gb  = round(usage.free / (1024 ** 3), 1)
        checks["disk_free_gb"] = free_gb
        checks["disk"]         = "ok" if free_gb > 1.0 else "warning: low disk space"
    except Exception:
        checks["disk"] = "unknown"

    overall = "online" if checks["database"] == "ok" else "degraded"

    return {
        "status":     overall,
        "system":     "NXIO",
        "version":    "3.0.0",
        "timestamp":  datetime.now().strftime("%d %b %Y %H:%M:%S"),
        "env":        settings.nxio_env,
        "checks":     checks,
        "symbols":    list(NSE_SYMBOLS.keys()),
        "timeframes": list(TIMEFRAMES.keys()),
    }


# ── Signal Endpoints ──────────────────────────────────────
@app.get("/signal")
def get_signal(asset: str = Query(default="RELIANCE"), tf: str = Query(default="5m")):
    asset = asset.upper()
    if asset not in NSE_SYMBOLS:
        return {"error": f"Unknown symbol: {asset}", "valid": list(NSE_SYMBOLS.keys())}
    if tf not in TIMEFRAMES:
        return {"error": f"Unknown timeframe: {tf}", "valid": list(TIMEFRAMES.keys())}
    signal = generate_signal(asset, timeframe=tf)
    if signal is None:
        return {"error": "Signal generation failed", "symbol": asset, "tf": tf}
    return signal


@app.get("/scan")
def get_scan(tf: str = Query(default="5m")):
    if tf not in TIMEFRAMES:
        return {"error": f"Unknown timeframe: {tf}"}
    signals   = scan_all(timeframe=tf)
    tradeable = [s for s in signals if s.get("valid")]
    return {
        "timeframe": tf,
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M:%S"),
        "total":     len(signals),
        "tradeable": len(tradeable),
        "signals":   signals,
    }


@app.get("/candles")
def get_candles(
    asset: str = Query(default="RELIANCE"),
    tf:    str = Query(default="5m"),
    n:     int = Query(default=60),
):
    asset  = asset.upper()
    tf_cfg = TIMEFRAMES.get(tf)
    if not tf_cfg:
        return {"error": f"Unknown timeframe: {tf}"}
    tf_label = tf_cfg["label"]
    path     = os.path.join(PROC_DIR, tf_label, f"{asset}_features.csv")
    if not os.path.exists(path):
        return {"error": f"No data for {asset} {tf_label}"}
    df      = pd.read_csv(path, index_col="Datetime", parse_dates=True).tail(n)
    candles = []
    for dt, row in df.iterrows():
        candles.append({
            "datetime":  str(dt),
            "open":      round(float(row.get("Open",   0)), 2),
            "high":      round(float(row.get("High",   0)), 2),
            "low":       round(float(row.get("Low",    0)), 2),
            "close":     round(float(row.get("Close",  0)), 2),
            "volume":    int(row.get("Volume", 0)),
            "rsi":       round(float(row.get("RSI",   50)), 2) if "RSI"       in row.index else None,
            "macd":      round(float(row.get("MACD",   0)), 4) if "MACD"      in row.index else None,
            "ema9":      round(float(row.get("EMA_9",  0)), 2) if "EMA_9"     in row.index else None,
            "ema21":     round(float(row.get("EMA_21", 0)), 2) if "EMA_21"    in row.index else None,
            "atr":       round(float(row.get("ATR",    0)), 2) if "ATR"       in row.index else None,
            "vwap":      round(float(row.get("VWAP",   0)), 2) if "VWAP"      in row.index else None,
            "vol_spike": int(row.get("Vol_spike", 0))          if "Vol_spike" in row.index else 0,
            "bb_upper":  round(float(row.get("BB_upper", 0)), 2) if "BB_upper" in row.index else None,
            "bb_lower":  round(float(row.get("BB_lower", 0)), 2) if "BB_lower" in row.index else None,
        })
    return {"asset": asset, "tf": tf_label, "count": len(candles), "candles": candles}


@app.get("/predict")
def get_predict(
    asset:   str = Query(default="RELIANCE"),
    tf:      str = Query(default="5m"),
    candles: int = Query(default=5),
):
    asset = asset.upper()
    if asset not in NSE_SYMBOLS:
        return {"error": f"Unknown symbol: {asset}"}
    if tf not in TIMEFRAMES:
        return {"error": f"Unknown timeframe: {tf}"}
    preds = predict_next_candles(asset, timeframe=tf, n_candles=candles)
    if preds is None:
        return {"error": "Prediction failed", "symbol": asset, "tf": tf}
    ups   = sum(1 for p in preds if p["direction"] == "UP")
    downs = candles - ups
    trend = "BULLISH" if ups > downs else "BEARISH" if downs > ups else "NEUTRAL"
    return {
        "asset":       asset,
        "timeframe":   tf,
        "timestamp":   datetime.now().strftime("%d %b %Y %H:%M:%S"),
        "base_price":  preds[0]["from_price"],
        "n_candles":   candles,
        "trend":       trend,
        "ups":         ups,
        "downs":       downs,
        "predictions": preds,
    }


# ── Paper Trading Endpoints ───────────────────────────────
@app.post("/paper/buy", dependencies=[Depends(verify_api_key)])
def paper_buy(req: BuyRequest):
    require_paper_mode()
    return buy_stock(
        symbol=req.symbol, price=req.price, quantity=req.quantity,
        signal_conf=req.confidence, sl=req.sl, tp=req.tp,
        idempotency_key=req.idempotency_key,
    )


@app.post("/paper/sell", dependencies=[Depends(verify_api_key)])
def paper_sell(req: SellRequest):
    require_paper_mode()
    return sell_stock(symbol=req.symbol, price=req.price, quantity=req.quantity)


@app.get("/paper/portfolio")
def paper_portfolio():
    return get_portfolio_summary()


@app.get("/paper/orders")
def paper_orders():
    orders = load_orders()
    return {"orders": orders, "count": len(orders)}


@app.get("/paper/history")
def paper_history():
    history   = load_history()
    total_pnl = sum(t["pnl"] for t in history)
    wins      = [t for t in history if t["result"] == "WIN"]
    losses    = [t for t in history if t["result"] == "LOSS"]
    return {
        "history":   history,
        "total":     len(history),
        "wins":      len(wins),
        "losses":    len(losses),
        "win_rate":  round(len(wins) / len(history) * 100, 1) if history else 0,
        "total_pnl": round(total_pnl, 2),
    }


@app.post("/paper/reset", dependencies=[Depends(verify_api_key)])
def paper_reset():
    require_paper_mode()
    return reset_portfolio()


@app.get("/symbols")
def get_symbols():
    return {
        "nse":        list(NSE_SYMBOLS.keys()),
        "tf":         list(TIMEFRAMES.keys()),
        "default_tf": "5m",
    }
# ============================================================
#  NEXUS INDIA — api/server.py (Paper Trading Added)
# ============================================================
import os, sys
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NSE_SYMBOLS, TIMEFRAMES, MIN_CONFIDENCE, PROC_DIR
from signals.generator import generate_signal, scan_all
from brain.predictor import predict_next_candles
from paper_trading.portfolio import (
    buy_stock, sell_stock, get_portfolio_summary,
    load_orders, load_history, reset_portfolio
)
app = FastAPI(title="NEXUS India API", version="3.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
# ── Request Models ────────────────────────────────────────
class BuyRequest(BaseModel):
    symbol:     str
    price:      float
    quantity:   int
    sl:         float = None
    tp:         float = None
    confidence: float = None
class SellRequest(BaseModel):
    symbol:   str
    price:    float
    quantity: int
# ── Existing Endpoints ────────────────────────────────────
@app.get("/health")
def health():
    return {"status":"online","system":"NEXUS India","version":"3.0.0",
            "timestamp":datetime.now().strftime("%d %b %Y %H:%M:%S"),
            "symbols":list(NSE_SYMBOLS.keys()),"timeframes":list(TIMEFRAMES.keys())}
@app.get("/signal")
def get_signal(asset:str=Query(default="RELIANCE"),tf:str=Query(default="5m")):
    asset=asset.upper()
    if asset not in NSE_SYMBOLS:
        return {"error":f"Unknown symbol: {asset}","valid":list(NSE_SYMBOLS.keys())}
    if tf not in TIMEFRAMES:
        return {"error":f"Unknown timeframe: {tf}","valid":list(TIMEFRAMES.keys())}
    signal=generate_signal(asset,timeframe=tf)
    if signal is None:
        return {"error":"Signal generation failed","symbol":asset,"tf":tf}
    return signal
@app.get("/scan")
def get_scan(tf:str=Query(default="5m")):
    if tf not in TIMEFRAMES:
        return {"error":f"Unknown timeframe: {tf}"}
    signals=scan_all(timeframe=tf)
    tradeable=[s for s in signals if s.get("valid")]
    return {"timeframe":tf,"timestamp":datetime.now().strftime("%d %b %Y %H:%M:%S"),
            "total":len(signals),"tradeable":len(tradeable),"signals":signals}
@app.get("/candles")
def get_candles(asset:str=Query(default="RELIANCE"),tf:str=Query(default="5m"),n:int=Query(default=60)):
    asset=asset.upper()
    tf_cfg=TIMEFRAMES.get(tf)
    if not tf_cfg:
        return {"error":f"Unknown timeframe: {tf}"}
    tf_label=tf_cfg["label"]
    path=os.path.join(PROC_DIR,tf_label,f"{asset}_features.csv")
    if not os.path.exists(path):
        return {"error":f"No data for {asset} {tf_label}"}
    df=pd.read_csv(path,index_col="Datetime",parse_dates=True).tail(n)
    candles=[]
    for dt,row in df.iterrows():
        candles.append({
            "datetime": str(dt),
            "open":     round(float(row.get("Open",  0)),2),
            "high":     round(float(row.get("High",  0)),2),
            "low":      round(float(row.get("Low",   0)),2),
            "close":    round(float(row.get("Close", 0)),2),
            "volume":   int(row.get("Volume",0)),
            "rsi":      round(float(row.get("RSI",  50)),2) if "RSI"       in row.index else None,
            "macd":     round(float(row.get("MACD",  0)),4) if "MACD"      in row.index else None,
            "ema9":     round(float(row.get("EMA_9", 0)),2) if "EMA_9"     in row.index else None,
            "ema21":    round(float(row.get("EMA_21",0)),2) if "EMA_21"    in row.index else None,
            "atr":      round(float(row.get("ATR",   0)),2) if "ATR"       in row.index else None,
            "vwap":     round(float(row.get("VWAP",  0)),2) if "VWAP"      in row.index else None,
            "vol_spike":int(row.get("Vol_spike",0))         if "Vol_spike" in row.index else 0,
            "bb_upper": round(float(row.get("BB_upper",0)),2) if "BB_upper" in row.index else None,
            "bb_lower": round(float(row.get("BB_lower",0)),2) if "BB_lower" in row.index else None,
        })
    return {"asset":asset,"tf":tf_label,"count":len(candles),"candles":candles}
@app.get("/predict")
def get_predict(asset:str=Query(default="RELIANCE"),tf:str=Query(default="5m"),candles:int=Query(default=5)):
    asset=asset.upper()
    if asset not in NSE_SYMBOLS:
        return {"error":f"Unknown symbol: {asset}"}
    if tf not in TIMEFRAMES:
        return {"error":f"Unknown timeframe: {tf}"}
    preds=predict_next_candles(asset,timeframe=tf,n_candles=candles)
    if preds is None:
        return {"error":"Prediction failed","symbol":asset,"tf":tf}
    ups=sum(1 for p in preds if p["direction"]=="UP")
    downs=candles-ups
    trend="BULLISH" if ups>downs else "BEARISH" if downs>ups else "NEUTRAL"
    return {"asset":asset,"timeframe":tf,
            "timestamp":datetime.now().strftime("%d %b %Y %H:%M:%S"),
            "base_price":preds[0]["from_price"],"n_candles":candles,
            "trend":trend,"ups":ups,"downs":downs,"predictions":preds}
# ── Paper Trading Endpoints ───────────────────────────────
@app.post("/paper/buy")
def paper_buy(req: BuyRequest):
    result = buy_stock(
        symbol=req.symbol.upper(),
        price=req.price,
        quantity=req.quantity,
        signal_conf=req.confidence,
        sl=req.sl,
        tp=req.tp,
    )
    return result
@app.post("/paper/sell")
def paper_sell(req: SellRequest):
    result = sell_stock(
        symbol=req.symbol.upper(),
        price=req.price,
        quantity=req.quantity,
    )
    return result
@app.get("/paper/portfolio")
def paper_portfolio():
    summary = get_portfolio_summary()
    return summary
@app.get("/paper/orders")
def paper_orders():
    orders = load_orders()
    return {"orders": orders, "count": len(orders)}
@app.get("/paper/history")
def paper_history():
    history = load_history()
    total_pnl = sum(t["pnl"] for t in history)
    wins  = [t for t in history if t["result"] == "WIN"]
    losses= [t for t in history if t["result"] == "LOSS"]
    return {
        "history":    history,
        "total":      len(history),
        "wins":       len(wins),
        "losses":     len(losses),
        "win_rate":   round(len(wins)/len(history)*100,1) if history else 0,
        "total_pnl":  round(total_pnl, 2),
    }
@app.post("/paper/reset")
def paper_reset():
    return reset_portfolio()
@app.get("/symbols")
def get_symbols():
    return {"nse":list(NSE_SYMBOLS.keys()),"tf":list(TIMEFRAMES.keys()),"default_tf":"5m"}

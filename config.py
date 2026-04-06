# ============================================================
#  NEXUS INDIA — config.py
# ============================================================
import os
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_DIR   = os.path.join(BASE_DIR, "data")
RAW_DIR    = os.path.join(DATA_DIR, "raw")
PROC_DIR   = os.path.join(DATA_DIR, "processed")
LIVE_DIR   = os.path.join(DATA_DIR, "live")
MODEL_DIR  = os.path.join(BASE_DIR, "brain", "models")
LOG_DIR    = os.path.join(BASE_DIR, "logs")
DEFAULT_TIMEFRAME = "5m"
TIMEFRAMES = {
    "1m":  {"label": "1M",  "seconds": 60,   "conf_boost": 0,  "yf_interval": "1m",  "yf_period": "7d"},
    "5m":  {"label": "5M",  "seconds": 300,  "conf_boost": 3,  "yf_interval": "5m",  "yf_period": "60d"},
    "15m": {"label": "15M", "seconds": 900,  "conf_boost": 5,  "yf_interval": "15m", "yf_period": "60d"},
    "1h":  {"label": "1H",  "seconds": 3600, "conf_boost": 7,  "yf_interval": "1h",  "yf_period": "730d"},
}
NSE_SYMBOLS = {
    "RELIANCE":  "RELIANCE.NS",
    "TCS":       "TCS.NS",
    "HDFCBANK":  "HDFCBANK.NS",
}
INDEX_SYMBOLS = {
    "NIFTY50":   "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX":    "^BSESN",
}
MCX_SYMBOLS = {
    "GOLD":     "GC=F",
    "SILVER":   "SI=F",
    "CRUDEOIL": "CL=F",
}
CROSS_MARKET = {
    "USD_INR":   "INR=X",
    "DOW":       "^DJI",
    "NIKKEI":    "^N225",
    "VIX_INDIA": "^INDIAVIX",
}
NSE_OPEN  = "09:15"
NSE_CLOSE = "15:30"
NSE_TZ    = "Asia/Kolkata"
RISK_CONFIG = {
    "1m":  {"sl_pts": 15,  "tp_pts": 15,  "max_trades": 5, "capital_pct": 1},
    "5m":  {"sl_pts": 55,  "tp_pts": 125, "max_trades": 4, "capital_pct": 2},
    "15m": {"sl_pts": 105, "tp_pts": 275, "max_trades": 2, "capital_pct": 3},
    "1h":  {"sl_pts": 200, "tp_pts": 500, "max_trades": 2, "capital_pct": 5},
}
# ── Improved training settings ────────────────────────────
LOOKBACK_CANDLES = 30       # reduced from 60 — better for limited data
TRAIN_SPLIT      = 0.8
LSTM_EPOCHS      = 150      # increased from 50
LSTM_BATCH_SIZE  = 16       # smaller batch — better gradient updates
MIN_CONFIDENCE   = 60

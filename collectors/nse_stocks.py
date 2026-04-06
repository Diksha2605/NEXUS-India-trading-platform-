# ============================================================
#  NEXUS INDIA — collectors/nse_stocks.py
#  Fetches NSE stock OHLCV data for all 4 timeframes
# ============================================================
import os, sys
import yfinance as yf
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import NSE_SYMBOLS, TIMEFRAMES, RAW_DIR
def log(msg, level="INFO"):
    colors = {"INFO": Fore.CYAN, "OK": Fore.GREEN, "WARN": Fore.YELLOW, "ERR": Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level, Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
def get_save_path(symbol_clean, tf_label):
    folder = os.path.join(RAW_DIR, tf_label)
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{symbol_clean}.csv")
def fetch_nse_stock(symbol_clean, timeframe="5m", save=True):
    if timeframe not in TIMEFRAMES:
        log(f"Unknown timeframe: {timeframe}", "ERR")
        return None
    tf_cfg    = TIMEFRAMES[timeframe]
    yf_symbol = NSE_SYMBOLS.get(symbol_clean)
    if not yf_symbol:
        log(f"Symbol '{symbol_clean}' not in config.NSE_SYMBOLS", "ERR")
        return None
    log(f"Fetching {symbol_clean} ({yf_symbol}) — {tf_cfg['label']} candles ...")
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            period=tf_cfg["yf_period"],
            interval=tf_cfg["yf_interval"],
            auto_adjust=True,
            prepost=False,
        )
        if df.empty:
            log(f"No data returned for {yf_symbol} on {tf_cfg['label']}", "WARN")
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
        df.index.name = "Datetime"
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = df[col].round(2)
        log(f"{symbol_clean} {tf_cfg['label']} — {len(df)} candles | "
            f"{df.index[0].strftime('%d %b %Y')} to {df.index[-1].strftime('%d %b %Y %H:%M')}", "OK")
        if save:
            path = get_save_path(symbol_clean, tf_cfg["label"])
            df.to_csv(path)
            log(f"Saved => {path}", "OK")
        return df
    except Exception as e:
        log(f"Error fetching {yf_symbol}: {e}", "ERR")
        return None
def fetch_all_timeframes(symbol_clean, save=True):
    results = {}
    log(f"\n{'='*50}")
    log(f"  FETCHING ALL TIMEFRAMES — {symbol_clean}")
    log(f"{'='*50}")
    for tf in TIMEFRAMES:
        df = fetch_nse_stock(symbol_clean, timeframe=tf, save=save)
        results[tf] = df
    success = sum(1 for v in results.values() if v is not None)
    log(f"{symbol_clean} — {success}/{len(TIMEFRAMES)} timeframes done.\n", "OK")
    return results
def fetch_all_stocks(save=True):
    all_data = {}
    log(f"\n{'='*50}")
    log(f"  NEXUS INDIA — NSE STOCK COLLECTION")
    log(f"  Stocks : {list(NSE_SYMBOLS.keys())}")
    log(f"{'='*50}\n")
    for i, symbol in enumerate(NSE_SYMBOLS, 1):
        log(f"[{i}/{len(NSE_SYMBOLS)}] Starting {symbol} ...")
        all_data[symbol] = fetch_all_timeframes(symbol, save=save)
    return all_data
def load_nse_stock(symbol_clean, timeframe="5m"):
    tf_cfg = TIMEFRAMES.get(timeframe)
    if not tf_cfg:
        log(f"Invalid timeframe: {timeframe}", "ERR")
        return None
    path = get_save_path(symbol_clean, tf_cfg["label"])
    if not os.path.exists(path):
        log(f"File not found: {path} — run fetch first.", "WARN")
        return None
    df = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    log(f"Loaded {symbol_clean} {tf_cfg['label']} — {len(df)} rows", "OK")
    return df
def print_summary():
    log("\n── DATA SUMMARY ──────────────────────────────────────")
    for tf, cfg in TIMEFRAMES.items():
        folder = os.path.join(RAW_DIR, cfg["label"])
        if os.path.exists(folder):
            files = [f for f in os.listdir(folder) if f.endswith(".csv")]
            for f in files:
                path = os.path.join(folder, f)
                df = pd.read_csv(path, index_col="Datetime", parse_dates=True)
                sym = f.replace(".csv", "")
                log(f"  {sym:<15} {cfg['label']:<4}  {len(df):>5} candles  "
                    f"| {df.index[0].strftime('%d %b %Y')} to {df.index[-1].strftime('%d %b %Y')}")
        else:
            log(f"  {cfg['label']} folder missing — not collected yet.", "WARN")
    log("")
if __name__ == "__main__":
    fetch_all_stocks(save=True)
    print_summary()

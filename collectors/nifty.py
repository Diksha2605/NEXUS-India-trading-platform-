# ============================================================
#  NEXUS INDIA — collectors/nifty.py
#  Fetches NIFTY 50, BANK NIFTY, SENSEX index data
# ============================================================
import os, sys
import yfinance as yf
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import INDEX_SYMBOLS, TIMEFRAMES, RAW_DIR
def log(msg, level="INFO"):
    colors = {"INFO": Fore.CYAN, "OK": Fore.GREEN, "WARN": Fore.YELLOW, "ERR": Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level, Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
def fetch_index(index_name, timeframe="5m", save=True):
    if timeframe not in TIMEFRAMES:
        log(f"Unknown timeframe: {timeframe}", "ERR")
        return None
    tf_cfg    = TIMEFRAMES[timeframe]
    yf_symbol = INDEX_SYMBOLS.get(index_name)
    if not yf_symbol:
        log(f"'{index_name}' not in config.INDEX_SYMBOLS", "ERR")
        return None
    log(f"Fetching {index_name} ({yf_symbol}) — {tf_cfg['label']} ...")
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            period=tf_cfg["yf_period"],
            interval=tf_cfg["yf_interval"],
            auto_adjust=True,
        )
        if df.empty:
            log(f"No data for {yf_symbol}", "WARN")
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        df.index = pd.to_datetime(df.index)
        df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
        df.index.name = "Datetime"
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = df[col].round(2)
        log(f"{index_name} {tf_cfg['label']} — {len(df)} candles | "
            f"{df.index[0].strftime('%d %b %Y')} to {df.index[-1].strftime('%d %b %Y %H:%M')}", "OK")
        if save:
            folder = os.path.join(RAW_DIR, tf_cfg["label"])
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"{index_name}.csv")
            df.to_csv(path)
            log(f"Saved => {path}", "OK")
        return df
    except Exception as e:
        log(f"Error: {e}", "ERR")
        return None
def fetch_all_indices(save=True):
    log("\n── FETCHING ALL INDICES ──────────────────────────────")
    all_data = {}
    for index_name in INDEX_SYMBOLS:
        all_data[index_name] = {}
        for tf in TIMEFRAMES:
            df = fetch_index(index_name, timeframe=tf, save=save)
            all_data[index_name][tf] = df
    return all_data
if __name__ == "__main__":
    fetch_all_indices(save=True)

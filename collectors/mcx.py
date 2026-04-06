# ============================================================
#  NEXUS INDIA — collectors/mcx.py
#  MCX commodities via COMEX/NYMEX yfinance proxies
#  Gold=GC=F  Silver=SI=F  Crude=CL=F
# ============================================================
import os, sys
import yfinance as yf
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import MCX_SYMBOLS, TIMEFRAMES, RAW_DIR
def log(msg, level="INFO"):
    colors = {"INFO": Fore.CYAN, "OK": Fore.GREEN, "WARN": Fore.YELLOW, "ERR": Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level, Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
def fetch_mcx(commodity, timeframe="5m", save=True):
    if timeframe not in TIMEFRAMES:
        log(f"Unknown timeframe: {timeframe}", "ERR")
        return None
    tf_cfg    = TIMEFRAMES[timeframe]
    yf_symbol = MCX_SYMBOLS.get(commodity)
    if not yf_symbol:
        log(f"'{commodity}' not in config.MCX_SYMBOLS", "ERR")
        return None
    log(f"Fetching MCX {commodity} ({yf_symbol} proxy) — {tf_cfg['label']} ...")
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
        try:
            df.index = df.index.tz_convert("Asia/Kolkata").tz_localize(None)
        except Exception:
            df.index = df.index.tz_localize(None)
        df.index.name = "Datetime"
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = df[col].round(2)
        log(f"MCX {commodity} {tf_cfg['label']} — {len(df)} candles | "
            f"{df.index[0].strftime('%d %b %Y')} to {df.index[-1].strftime('%d %b %Y %H:%M')}", "OK")
        if save:
            folder = os.path.join(RAW_DIR, tf_cfg["label"])
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, f"MCX_{commodity}.csv")
            df.to_csv(path)
            log(f"Saved => {path}", "OK")
        return df
    except Exception as e:
        log(f"Error: {e}", "ERR")
        return None
def fetch_all_mcx(save=True):
    log("\n── FETCHING ALL MCX COMMODITIES ──────────────────────")
    all_data = {}
    for commodity in MCX_SYMBOLS:
        all_data[commodity] = {}
        for tf in TIMEFRAMES:
            df = fetch_mcx(commodity, timeframe=tf, save=save)
            all_data[commodity][tf] = df
    return all_data
if __name__ == "__main__":
    fetch_all_mcx(save=True)

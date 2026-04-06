# ============================================================
#  NEXUS INDIA — brain/features.py
#  Phase 2: Feature Engineering
#  Adds RSI, MACD, Bollinger Bands, EMA, VWAP to raw OHLCV
#  Input:  data/raw/<TF>/<symbol>.csv
#  Output: data/processed/<TF>/<symbol>_features.csv
# ============================================================
import os, sys
import pandas as pd
import numpy as np
import ta
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (NSE_SYMBOLS, INDEX_SYMBOLS, MCX_SYMBOLS,
                    TIMEFRAMES, RAW_DIR, PROC_DIR)
def log(msg, level="INFO"):
    colors = {"INFO": Fore.CYAN, "OK": Fore.GREEN, "WARN": Fore.YELLOW, "ERR": Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level, Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
# ── Core Feature Builder ──────────────────────────────────────
def add_features(df):
    """
    Takes a raw OHLCV DataFrame and returns it with
    all technical indicators added as new columns.
    """
    df = df.copy()
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]
    # ── Trend Indicators ─────────────────────────────────────
    # EMA — Exponential Moving Averages
    df["EMA_9"]  = ta.trend.ema_indicator(close, window=9)
    df["EMA_21"] = ta.trend.ema_indicator(close, window=21)
    df["EMA_50"] = ta.trend.ema_indicator(close, window=50)
    # EMA Cross signal: 1 = bullish cross, -1 = bearish, 0 = none
    df["EMA_cross"] = np.where(df["EMA_9"] > df["EMA_21"], 1, -1)
    # MACD
    macd_obj        = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["MACD"]      = macd_obj.macd()
    df["MACD_sig"]  = macd_obj.macd_signal()
    df["MACD_hist"] = macd_obj.macd_diff()
    # MACD cross: 1 = MACD crossed above signal, -1 = below
    df["MACD_cross"] = np.where(df["MACD"] > df["MACD_sig"], 1, -1)
    # ADX — Trend strength (>25 = strong trend)
    adx_obj    = ta.trend.ADXIndicator(high, low, close, window=14)
    df["ADX"]  = adx_obj.adx()
    df["DI_pos"] = adx_obj.adx_pos()
    df["DI_neg"] = adx_obj.adx_neg()
    # ── Momentum Indicators ───────────────────────────────────
    # RSI — Relative Strength Index
    df["RSI"] = ta.momentum.RSIIndicator(close, window=14).rsi()
    # RSI zones: oversold=1, overbought=-1, neutral=0
    df["RSI_zone"] = np.where(df["RSI"] < 35, 1,
                     np.where(df["RSI"] > 65, -1, 0))
    # Stochastic Oscillator
    stoch_obj      = ta.momentum.StochasticOscillator(high, low, close, window=14)
    df["STOCH_k"]  = stoch_obj.stoch()
    df["STOCH_d"]  = stoch_obj.stoch_signal()
    # ROC — Rate of Change
    df["ROC"] = ta.momentum.ROCIndicator(close, window=10).roc()
    # ── Volatility Indicators ─────────────────────────────────
    # Bollinger Bands
    bb_obj          = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["BB_upper"]  = bb_obj.bollinger_hband()
    df["BB_lower"]  = bb_obj.bollinger_lband()
    df["BB_mid"]    = bb_obj.bollinger_mavg()
    df["BB_width"]  = (df["BB_upper"] - df["BB_lower"]) / df["BB_mid"]
    # BB position: where is price relative to bands? 0=lower, 1=upper
    df["BB_pos"] = (close - df["BB_lower"]) / (df["BB_upper"] - df["BB_lower"] + 1e-9)
    # ATR — Average True Range (volatility measure)
    df["ATR"] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    # ── Volume Indicators ─────────────────────────────────────
    # VWAP — Volume Weighted Average Price
    # Rolling VWAP (true VWAP resets daily; this is a 20-period proxy)
    tp = (high + low + close) / 3
    df["VWAP"] = (tp * vol).rolling(20).sum() / vol.rolling(20).sum()
    # Price vs VWAP: 1 = above (bullish), -1 = below (bearish)
    df["VWAP_signal"] = np.where(close > df["VWAP"], 1, -1)
    # OBV — On Balance Volume
    df["OBV"] = ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()
    # Volume spike: is current volume > 1.5x 20-period avg?
    df["Vol_avg"]   = vol.rolling(20).mean()
    df["Vol_spike"] = np.where(vol > df["Vol_avg"] * 1.5, 1, 0)
    # ── Price Action Features ─────────────────────────────────
    # Candle body size (% of range)
    df["Body_size"] = abs(close - df["Open"]) / (high - low + 1e-9)
    # Candle direction: 1 = green, -1 = red
    df["Candle_dir"] = np.where(close >= df["Open"], 1, -1)
    # Distance from 52-week high/low (%)
    df["Pct_from_high"] = (close - close.rolling(252).max()) / close.rolling(252).max() * 100
    df["Pct_from_low"]  = (close - close.rolling(252).min()) / close.rolling(252).min() * 100
    # ── Target Label (for LSTM training) ─────────────────────
    # 1 = next candle closes higher, 0 = next candle closes lower
    df["Target"] = np.where(close.shift(-1) > close, 1, 0)
    # ── Clean up ─────────────────────────────────────────────
    df.dropna(inplace=True)
    df = df.round(4)
    return df
# ── Process One File ──────────────────────────────────────────
def process_symbol(symbol, tf_label, save=True):
    """
    Load raw CSV, add features, save to processed folder.
    Args:
        symbol   (str): e.g. "RELIANCE", "NIFTY50", "MCX_GOLD"
        tf_label (str): "1M" | "5M" | "15M" | "1H"
        save    (bool): Save to data/processed/<TF>/
    Returns:
        pd.DataFrame or None
    """
    raw_path = os.path.join(RAW_DIR, tf_label, f"{symbol}.csv")
    if not os.path.exists(raw_path):
        log(f"Raw file not found: {raw_path}", "WARN")
        return None
    log(f"Processing {symbol} {tf_label} ...")
    df = pd.read_csv(raw_path, index_col="Datetime", parse_dates=True)
    if len(df) < 60:
        log(f"{symbol} {tf_label} — too few rows ({len(df)}), skipping.", "WARN")
        return None
    df_feat = add_features(df)
    feature_cols = [c for c in df_feat.columns if c not in ["Open","High","Low","Close","Volume"]]
    log(f"{symbol} {tf_label} — {len(df_feat)} rows | {len(feature_cols)} features added", "OK")
    if save:
        out_folder = os.path.join(PROC_DIR, tf_label)
        os.makedirs(out_folder, exist_ok=True)
        out_path = os.path.join(out_folder, f"{symbol}_features.csv")
        df_feat.to_csv(out_path)
        log(f"Saved => {out_path}", "OK")
    return df_feat
# ── Process All Symbols ───────────────────────────────────────
def process_all(save=True):
    """
    Process all NSE stocks, indices, and MCX commodities
    across all 4 timeframes.
    """
    log(f"\n{'='*55}")
    log(f"  NEXUS INDIA — PHASE 2: FEATURE ENGINEERING")
    log(f"{'='*55}\n")
    all_symbols = (
        list(NSE_SYMBOLS.keys()) +
        list(INDEX_SYMBOLS.keys()) +
        [f"MCX_{c}" for c in MCX_SYMBOLS.keys()]
    )
    results = {}
    total   = len(all_symbols) * len(TIMEFRAMES)
    done    = 0
    for symbol in all_symbols:
        results[symbol] = {}
        for tf, cfg in TIMEFRAMES.items():
            df = process_symbol(symbol, cfg["label"], save=save)
            results[symbol][tf] = df
            done += 1
            log(f"  Progress: {done}/{total}", "INFO")
    log(f"\n{'='*55}", "OK")
    log(f"  PHASE 2 COMPLETE — All features generated", "OK")
    log(f"  Saved in: data/processed/", "OK")
    log(f"{'='*55}\n", "OK")
    return results
# ── Print Feature List ────────────────────────────────────────
def print_features():
    """Show all features that will be generated."""
    features = {
        "Trend":     ["EMA_9", "EMA_21", "EMA_50", "EMA_cross", "MACD",
                      "MACD_sig", "MACD_hist", "MACD_cross", "ADX", "DI_pos", "DI_neg"],
        "Momentum":  ["RSI", "RSI_zone", "STOCH_k", "STOCH_d", "ROC"],
        "Volatility":["BB_upper", "BB_lower", "BB_mid", "BB_width", "BB_pos", "ATR"],
        "Volume":    ["VWAP", "VWAP_signal", "OBV", "Vol_avg", "Vol_spike"],
        "Price":     ["Body_size", "Candle_dir", "Pct_from_high", "Pct_from_low"],
        "Target":    ["Target (1=UP next candle, 0=DOWN)"],
    }
    log("\n── FEATURES TO BE GENERATED ──────────────────────────")
    for category, feats in features.items():
        log(f"  {category:<12}: {', '.join(feats)}")
    log(f"\n  Total: ~{sum(len(v) for v in features.values())} features per candle\n")
# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    print_features()
    process_all(save=True)

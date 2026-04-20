# ============================================================
#  NXIO — brain/predictor.py
#  Multi-Candle Prediction Engine
#  Predicts next 5 candles direction + price targets
# ============================================================
import os, sys
import numpy as np
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (NSE_SYMBOLS, TIMEFRAMES, PROC_DIR,
                    MODEL_DIR, LOOKBACK_CANDLES)
def log(msg, level="INFO"):
    colors = {"INFO":Fore.CYAN,"OK":Fore.GREEN,"WARN":Fore.YELLOW,"ERR":Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level,Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
def load_model_and_scaler(symbol, timeframe="5m"):
    import tensorflow as tf
    model_path  = os.path.join(MODEL_DIR, f"lstm_{symbol.lower()}_{timeframe}.h5")
    scaler_path = os.path.join(MODEL_DIR, f"scaler_{symbol.lower()}_{timeframe}.npz")
    if not os.path.exists(model_path):
        log(f"Model not found: {model_path}", "WARN")
        return None, None
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = tf.keras.models.load_model(model_path)
    scaler = None
    if os.path.exists(scaler_path):
        data   = np.load(scaler_path, allow_pickle=True)
        scaler = {"median":data["median"],"std":data["std"],"features":list(data["features"])}
    return model, scaler
def prepare_window(df, feature_cols, scaler):
    available = [c for c in feature_cols if c in df.columns]
    data      = df[available].dropna().values[-LOOKBACK_CANDLES:].astype(np.float32)
    if len(data) < LOOKBACK_CANDLES:
        return None
    if scaler:
        median = scaler["median"]
        std    = scaler["std"].copy(); std[std==0]=1
        data   = (data - median) / std
        data   = np.clip(data, -3, 3)
        data   = (data + 3) / 6
    return data
def predict_next_candles(symbol, timeframe="5m", n_candles=5):
    """
    Predict next N candles for a symbol.
    Returns list of dicts:
    [
      { candle: 1, direction: "UP", probability: 0.72,
        predicted_price: 2865.0, change_pct: 0.6 },
      ...
    ]
    """
    tf_cfg   = TIMEFRAMES.get(timeframe)
    if not tf_cfg:
        log(f"Unknown TF: {timeframe}", "ERR")
        return None
    tf_label = tf_cfg["label"]
    model, scaler = load_model_and_scaler(symbol, timeframe)
    if model is None:
        return None
    path = os.path.join(PROC_DIR, tf_label, f"{symbol}_features.csv")
    if not os.path.exists(path):
        log(f"Features file missing: {path}", "WARN")
        return None
    df = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    feature_cols = scaler["features"] if scaler else [c for c in df.columns if c != "Target"]
    last_close = float(df["Close"].iloc[-1]) if "Close" in df.columns else 0
    last_atr   = float(df["ATR"].iloc[-1])   if "ATR"   in df.columns else last_close * 0.005
    predictions = []
    sim_df      = df.copy()
    for i in range(1, n_candles + 1):
        window = prepare_window(sim_df, feature_cols, scaler)
        if window is None:
            break
        X    = window.reshape(1, LOOKBACK_CANDLES, window.shape[1])
        prob = float(model.predict(X, verbose=0)[0][0])
        direction = "UP" if prob >= 0.5 else "DOWN"
        conf      = prob if direction == "UP" else (1 - prob)
        # Estimate price move based on ATR
        move_pct   = (conf - 0.5) * 2 * (last_atr / last_close) * 100
        move_pct   = max(0.1, abs(move_pct))
        if direction == "UP":
            predicted_price = round(last_close * (1 + move_pct/100), 2)
        else:
            predicted_price = round(last_close * (1 - move_pct/100), 2)
        change_pts = round(predicted_price - last_close, 2)
        change_pct = round((predicted_price - last_close) / last_close * 100, 3)
        predictions.append({
            "candle":          i,
            "direction":       direction,
            "probability":     round(prob, 4),
            "confidence":      round(conf * 100, 1),
            "predicted_price": predicted_price,
            "change_pts":      change_pts,
            "change_pct":      change_pct,
            "from_price":      round(last_close, 2),
        })
        # Simulate next candle in df for rolling prediction
        new_row             = sim_df.iloc[-1:].copy()
        new_row.index       = [sim_df.index[-1] + pd.Timedelta(seconds=tf_cfg["seconds"])]
        new_row["Close"]    = predicted_price
        new_row["Open"]     = last_close
        new_row["High"]     = max(last_close, predicted_price) + last_atr * 0.2
        new_row["Low"]      = min(last_close, predicted_price) - last_atr * 0.2
        new_row["Target"]   = 1 if direction == "UP" else 0
        sim_df              = pd.concat([sim_df, new_row])
        last_close = predicted_price
    return predictions
def print_predictions(symbol, timeframe="5m", n_candles=5):
    preds = predict_next_candles(symbol, timeframe, n_candles)
    if not preds:
        log(f"Could not generate predictions for {symbol}", "WARN")
        return
    log(f"\n{'='*55}")
    log(f"  MULTI-CANDLE PREDICTION — {symbol} {timeframe.upper()}")
    log(f"  Base price: Rs.{preds[0]['from_price']}")
    log(f"{'='*55}")
    log(f"  {'CANDLE':<8} {'DIR':<6} {'PROB':>6} {'PRICE':>10} {'CHANGE':>8} {'CHG%':>7}")
    log(f"  {'-'*50}")
    for p in preds:
        arrow = "▲" if p["direction"] == "UP" else "▼"
        color = Fore.GREEN if p["direction"] == "UP" else Fore.RED
        sign  = "+" if p["change_pts"] >= 0 else ""
        log(f"  {color}Candle {p['candle']:<3}{Style.RESET_ALL} "
            f"{color}{arrow} {p['direction']:<5}{Style.RESET_ALL} "
            f"{p['confidence']:>5.1f}% "
            f"Rs.{p['predicted_price']:>9} "
            f"{sign}{p['change_pts']:>7} "
            f"{sign}{p['change_pct']:>6}%")
    log(f"{'='*55}\n")
    return preds
if __name__ == "__main__":
    for sym in ["RELIANCE", "TCS", "HDFCBANK"]:
        print_predictions(sym, timeframe="5m", n_candles=5)# ============================================================
#  NXIO — brain/predictor.py
#  Multi-Candle Prediction Engine
#  Predicts next 5 candles direction + price targets
# ============================================================
import os, sys
import numpy as np
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (NSE_SYMBOLS, TIMEFRAMES, PROC_DIR,
                    MODEL_DIR, LOOKBACK_CANDLES)
def log(msg, level="INFO"):
    colors = {"INFO":Fore.CYAN,"OK":Fore.GREEN,"WARN":Fore.YELLOW,"ERR":Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level,Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
def load_model_and_scaler(symbol, timeframe="5m"):
    import tensorflow as tf
    model_path  = os.path.join(MODEL_DIR, f"lstm_{symbol.lower()}_{timeframe}.h5")
    scaler_path = os.path.join(MODEL_DIR, f"scaler_{symbol.lower()}_{timeframe}.npz")
    if not os.path.exists(model_path):
        log(f"Model not found: {model_path}", "WARN")
        return None, None
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = tf.keras.models.load_model(model_path)
    scaler = None
    if os.path.exists(scaler_path):
        data   = np.load(scaler_path, allow_pickle=True)
        scaler = {"median":data["median"],"std":data["std"],"features":list(data["features"])}
    return model, scaler
def prepare_window(df, feature_cols, scaler):
    available = [c for c in feature_cols if c in df.columns]
    data      = df[available].dropna().values[-LOOKBACK_CANDLES:].astype(np.float32)
    if len(data) < LOOKBACK_CANDLES:
        return None
    if scaler:
        median = scaler["median"]
        std    = scaler["std"].copy(); std[std==0]=1
        data   = (data - median) / std
        data   = np.clip(data, -3, 3)
        data   = (data + 3) / 6
    return data
def predict_next_candles(symbol, timeframe="5m", n_candles=5):
    """
    Predict next N candles for a symbol.
    Returns list of dicts:
    [
      { candle: 1, direction: "UP", probability: 0.72,
        predicted_price: 2865.0, change_pct: 0.6 },
      ...
    ]
    """
    tf_cfg   = TIMEFRAMES.get(timeframe)
    if not tf_cfg:
        log(f"Unknown TF: {timeframe}", "ERR")
        return None
    tf_label = tf_cfg["label"]
    model, scaler = load_model_and_scaler(symbol, timeframe)
    if model is None:
        return None
    path = os.path.join(PROC_DIR, tf_label, f"{symbol}_features.csv")
    if not os.path.exists(path):
        log(f"Features file missing: {path}", "WARN")
        return None
    df = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    feature_cols = scaler["features"] if scaler else [c for c in df.columns if c != "Target"]
    last_close = float(df["Close"].iloc[-1]) if "Close" in df.columns else 0
    last_atr   = float(df["ATR"].iloc[-1])   if "ATR"   in df.columns else last_close * 0.005
    predictions = []
    sim_df      = df.copy()
    for i in range(1, n_candles + 1):
        window = prepare_window(sim_df, feature_cols, scaler)
        if window is None:
            break
        X    = window.reshape(1, LOOKBACK_CANDLES, window.shape[1])
        prob = float(model.predict(X, verbose=0)[0][0])
        direction = "UP" if prob >= 0.5 else "DOWN"
        conf      = prob if direction == "UP" else (1 - prob)
        # Estimate price move based on ATR
        move_pct   = (conf - 0.5) * 2 * (last_atr / last_close) * 100
        move_pct   = max(0.1, abs(move_pct))
        if direction == "UP":
            predicted_price = round(last_close * (1 + move_pct/100), 2)
        else:
            predicted_price = round(last_close * (1 - move_pct/100), 2)
        change_pts = round(predicted_price - last_close, 2)
        change_pct = round((predicted_price - last_close) / last_close * 100, 3)
        predictions.append({
            "candle":          i,
            "direction":       direction,
            "probability":     round(prob, 4),
            "confidence":      round(conf * 100, 1),
            "predicted_price": predicted_price,
            "change_pts":      change_pts,
            "change_pct":      change_pct,
            "from_price":      round(last_close, 2),
        })
        # Simulate next candle in df for rolling prediction
        new_row             = sim_df.iloc[-1:].copy()
        new_row.index       = [sim_df.index[-1] + pd.Timedelta(seconds=tf_cfg["seconds"])]
        new_row["Close"]    = predicted_price
        new_row["Open"]     = last_close
        new_row["High"]     = max(last_close, predicted_price) + last_atr * 0.2
        new_row["Low"]      = min(last_close, predicted_price) - last_atr * 0.2
        new_row["Target"]   = 1 if direction == "UP" else 0
        sim_df              = pd.concat([sim_df, new_row])
        last_close = predicted_price
    return predictions
def print_predictions(symbol, timeframe="5m", n_candles=5):
    preds = predict_next_candles(symbol, timeframe, n_candles)
    if not preds:
        log(f"Could not generate predictions for {symbol}", "WARN")
        return
    log(f"\n{'='*55}")
    log(f"  MULTI-CANDLE PREDICTION — {symbol} {timeframe.upper()}")
    log(f"  Base price: Rs.{preds[0]['from_price']}")
    log(f"{'='*55}")
    log(f"  {'CANDLE':<8} {'DIR':<6} {'PROB':>6} {'PRICE':>10} {'CHANGE':>8} {'CHG%':>7}")
    log(f"  {'-'*50}")
    for p in preds:
        arrow = "▲" if p["direction"] == "UP" else "▼"
        color = Fore.GREEN if p["direction"] == "UP" else Fore.RED
        sign  = "+" if p["change_pts"] >= 0 else ""
        log(f"  {color}Candle {p['candle']:<3}{Style.RESET_ALL} "
            f"{color}{arrow} {p['direction']:<5}{Style.RESET_ALL} "
            f"{p['confidence']:>5.1f}% "
            f"Rs.{p['predicted_price']:>9} "
            f"{sign}{p['change_pts']:>7} "
            f"{sign}{p['change_pct']:>6}%")
    log(f"{'='*55}\n")
    return preds
if __name__ == "__main__":
    for sym in ["RELIANCE", "TCS", "HDFCBANK"]:
        print_predictions(sym, timeframe="5m", n_candles=5)
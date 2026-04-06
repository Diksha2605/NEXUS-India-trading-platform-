# ============================================================
#  NEXUS INDIA — brain/lstm_model.py
#  Phase 3: LSTM Model Training (Improved)
# ============================================================
import os, sys
import numpy as np
import pandas as pd
from datetime import datetime
from colorama import Fore, Style, init
init(autoreset=True)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (NSE_SYMBOLS, TIMEFRAMES, PROC_DIR, MODEL_DIR,
                    LOOKBACK_CANDLES, TRAIN_SPLIT,
                    LSTM_EPOCHS, LSTM_BATCH_SIZE)
def log(msg, level="INFO"):
    colors = {"INFO": Fore.CYAN, "OK": Fore.GREEN,
              "WARN": Fore.YELLOW, "ERR": Fore.RED}
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"{Fore.WHITE}[{ts}] {colors.get(level, Fore.WHITE)}[{level}]{Style.RESET_ALL} {msg}")
FEATURE_COLS = [
    "Close", "Volume",
    "EMA_9", "EMA_21", "EMA_50", "EMA_cross",
    "MACD", "MACD_sig", "MACD_hist", "MACD_cross",
    "ADX", "DI_pos", "DI_neg",
    "RSI", "RSI_zone", "STOCH_k", "STOCH_d", "ROC",
    "BB_upper", "BB_lower", "BB_width", "BB_pos", "ATR",
    "VWAP", "VWAP_signal", "OBV", "Vol_spike",
    "Body_size", "Candle_dir",
]
TARGET_COL = "Target"
def load_and_prepare(symbol, tf_label):
    path = os.path.join(PROC_DIR, tf_label, f"{symbol}_features.csv")
    if not os.path.exists(path):
        log(f"File not found: {path}", "WARN")
        return None, None, None, None
    df = pd.read_csv(path, index_col="Datetime", parse_dates=True)
    available = [c for c in FEATURE_COLS if c in df.columns]
    if TARGET_COL not in df.columns:
        log(f"Target column missing", "ERR")
        return None, None, None, None
    df = df[available + [TARGET_COL]].dropna()
    if len(df) < LOOKBACK_CANDLES + 50:
        log(f"Not enough rows ({len(df)}) for {symbol} {tf_label}", "WARN")
        return None, None, None, None
    feature_data = df[available].values
    # ── Robust scaling (better than min-max for financial data) ──
    col_median = np.median(feature_data, axis=0)
    col_std    = feature_data.std(axis=0)
    col_std[col_std == 0] = 1
    feature_norm = (feature_data - col_median) / col_std
    # Clip extreme outliers
    feature_norm = np.clip(feature_norm, -3, 3)
    # Re-scale to 0-1 range
    feature_norm = (feature_norm + 3) / 6
    targets = df[TARGET_COL].values
    X, y = [], []
    for i in range(LOOKBACK_CANDLES, len(feature_norm)):
        X.append(feature_norm[i - LOOKBACK_CANDLES:i])
        y.append(targets[i])
    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.float32)
    # Save scaler params for inference
    scaler = {"median": col_median, "std": col_std}
    return X, y, available, scaler
def train_test_split_data(X, y):
    split = int(len(X) * TRAIN_SPLIT)
    return X[:split], X[split:], y[:split], y[split:]
def build_model(n_timesteps, n_features):
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import (Input, LSTM, Dense,
                                         Dropout, BatchNormalization)
    from tensorflow.keras.optimizers import Adam
    model = Sequential([
        Input(shape=(n_timesteps, n_features)),
        LSTM(64, return_sequences=True),
        BatchNormalization(),
        Dropout(0.3),
        LSTM(32, return_sequences=False),
        BatchNormalization(),
        Dropout(0.3),
        Dense(16, activation="relu"),
        Dropout(0.2),
        Dense(1, activation="sigmoid"),
    ])
    model.compile(
        optimizer=Adam(learning_rate=0.0005),
        loss="binary_crossentropy",
        metrics=["accuracy"],
    )
    return model
def train_model(symbol, timeframe="5m", save=True):
    tf_cfg = TIMEFRAMES.get(timeframe)
    if not tf_cfg:
        log(f"Unknown timeframe: {timeframe}", "ERR")
        return None
    tf_label = tf_cfg["label"]
    log(f"\nTraining LSTM — {symbol} {tf_label} ...")
    X, y, features, scaler = load_and_prepare(symbol, tf_label)
    if X is None:
        return None
    X_train, X_test, y_train, y_test = train_test_split_data(X, y)
    log(f"  Train samples : {len(X_train)}")
    log(f"  Test  samples : {len(X_test)}")
    log(f"  Features      : {X.shape[2]}")
    log(f"  Lookback      : {LOOKBACK_CANDLES} candles")
    model = build_model(n_timesteps=X.shape[1], n_features=X.shape[2])
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    callbacks = [
        EarlyStopping(
            monitor="val_accuracy",
            patience=15,
            restore_best_weights=True,
            verbose=0,
            mode="max"
        ),
        ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=7,
            verbose=0,
            min_lr=0.00001
        ),
    ]
    log(f"  Training for up to {LSTM_EPOCHS} epochs ...")
    history = model.fit(
        X_train, y_train,
        epochs=LSTM_EPOCHS,
        batch_size=LSTM_BATCH_SIZE,
        validation_split=0.15,
        callbacks=callbacks,
        verbose=0,
    )
    loss, acc = model.evaluate(X_test, y_test, verbose=0)
    epochs_run = len(history.history["loss"])
    # Best val accuracy during training
    best_val_acc = max(history.history["val_accuracy"]) * 100
    log(f"  Epochs run      : {epochs_run}", "OK")
    log(f"  Test Accuracy   : {acc*100:.1f}%", "OK")
    log(f"  Best Val Acc    : {best_val_acc:.1f}%", "OK")
    log(f"  Test Loss       : {loss:.4f}", "OK")
    result = {
        "symbol":       symbol,
        "timeframe":    tf_label,
        "accuracy":     round(acc * 100, 2),
        "best_val_acc": round(best_val_acc, 2),
        "loss":         round(loss, 4),
        "epochs":       epochs_run,
        "samples":      len(X),
    }
    if save:
        os.makedirs(MODEL_DIR, exist_ok=True)
        model_name = f"lstm_{symbol.lower()}_{timeframe}.h5"
        model_path = os.path.join(MODEL_DIR, model_name)
        model.save(model_path)
        log(f"  Saved => {model_path}", "OK")
        result["model_path"] = model_path
        # Save scaler params alongside model
        scaler_path = os.path.join(MODEL_DIR,
                      f"scaler_{symbol.lower()}_{timeframe}.npz")
        np.savez(scaler_path,
                 median=scaler["median"],
                 std=scaler["std"],
                 features=np.array(features))
        log(f"  Scaler => {scaler_path}", "OK")
    return result
def train_all(timeframes=None, symbols=None):
    if timeframes is None:
        timeframes = list(TIMEFRAMES.keys())
    if symbols is None:
        symbols = list(NSE_SYMBOLS.keys())
    log(f"\n{'='*55}")
    log(f"  NEXUS INDIA — PHASE 3: LSTM TRAINING (IMPROVED)")
    log(f"  Symbols    : {symbols}")
    log(f"  Timeframes : {timeframes}")
    log(f"  Lookback   : {LOOKBACK_CANDLES} candles")
    log(f"  Epochs     : up to {LSTM_EPOCHS}")
    log(f"  Batch size : {LSTM_BATCH_SIZE}")
    log(f"  Total runs : {len(symbols) * len(timeframes)}")
    log(f"{'='*55}\n")
    results = []
    total = len(symbols) * len(timeframes)
    done  = 0
    for symbol in symbols:
        for tf in timeframes:
            result = train_model(symbol, timeframe=tf, save=True)
            done += 1
            if result:
                results.append(result)
                log(f"  [{done}/{total}] {symbol} {result['timeframe']} "
                    f"— Test: {result['accuracy']}% "
                    f"| Best Val: {result['best_val_acc']}%", "OK")
            else:
                log(f"  [{done}/{total}] {symbol} {tf} — SKIPPED", "WARN")
    log(f"\n{'='*55}", "OK")
    log(f"  TRAINING COMPLETE — RESULTS SUMMARY", "OK")
    log(f"{'='*55}", "OK")
    log(f"  {'SYMBOL':<12} {'TF':<5} {'TEST ACC':>9} {'BEST VAL':>9} {'EPOCHS':>7}")
    log(f"  {'-'*50}")
    for r in results:
        log(f"  {r['symbol']:<12} {r['timeframe']:<5} "
            f"{r['accuracy']:>8.1f}% "
            f"{r['best_val_acc']:>8.1f}% "
            f"{r['epochs']:>7}")
    if results:
        avg_acc     = sum(r["accuracy"] for r in results) / len(results)
        avg_val_acc = sum(r["best_val_acc"] for r in results) / len(results)
        log(f"\n  Avg Test Accuracy : {avg_acc:.1f}%", "OK")
        log(f"  Avg Best Val Acc  : {avg_val_acc:.1f}%", "OK")
        log(f"  Models saved in   : brain/models/", "OK")
    log(f"{'='*55}\n", "OK")
    return results
if __name__ == "__main__":
    train_all(
        timeframes=["5m", "15m", "1h"],
        symbols=list(NSE_SYMBOLS.keys())
    )

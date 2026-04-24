# ============================================================
#  NXIO — brain/evaluate.py
#  Model Evaluation Report Generator
#  Run: python brain/evaluate.py
# ============================================================
import os, sys, json
import numpy as np
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "reports"
)
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")

SYMBOLS    = ["RELIANCE", "TCS", "HDFCBANK"]
TIMEFRAMES = ["5m", "15m", "1h"]
SYM_PREFIX = {"RELIANCE": "reliance", "TCS": "tcs", "HDFCBANK": "hdfcbank"}


def evaluate_model(symbol, tf):
    prefix = SYM_PREFIX[symbol]
    mpath  = os.path.join(MODELS_DIR, f"lstm_{prefix}_{tf}.h5")
    spath  = os.path.join(MODELS_DIR, f"scaler_{prefix}_{tf}.npz")

    result = {"symbol": symbol, "timeframe": tf,
              "timestamp": datetime.now().strftime("%d %b %Y %H:%M:%S"),
              "status": "skipped"}

    if not os.path.exists(mpath) or not os.path.exists(spath):
        result["error"] = "Model or scaler missing"
        return result

    try:
        import tensorflow as tf_lib
        from sklearn.preprocessing import MinMaxScaler
        from config import PROC_DIR, TIMEFRAMES as TF_CFG
        import pandas as pd

        # Load scaler
        sd     = np.load(spath, allow_pickle=True)
        scaler = MinMaxScaler()
        scaler.min_           = sd["min_"]
        scaler.scale_         = sd["scale_"]
        scaler.data_min_      = sd["data_min_"]
        scaler.data_max_      = sd["data_max_"]
        scaler.data_range_    = sd["data_range_"]
        scaler.n_features_in_ = int(sd["n_features_in_"])

        model    = tf_lib.keras.models.load_model(mpath, compile=False)
        tf_label = TF_CFG[tf]["label"]
        dpath    = os.path.join(PROC_DIR, tf_label, f"{symbol}_features.csv")

        if not os.path.exists(dpath):
            result["error"] = "No processed data found"
            return result

        df   = pd.read_csv(dpath, index_col="Datetime", parse_dates=True)
        COLS = [c for c in ["Open","High","Low","Close","Volume",
                             "RSI","MACD","EMA_9","EMA_21","ATR",
                             "VWAP","Vol_spike","BB_upper","BB_lower"]
                if c in df.columns]

        SEQ  = 60
        data = df[COLS].dropna().tail(200 + SEQ)
        if len(data) < SEQ + 10:
            result["error"] = "Not enough data"
            return result

        scaled = scaler.transform(data[COLS])
        X, y_true = [], []
        for i in range(SEQ, len(scaled) - 1):
            X.append(scaled[i - SEQ:i])
            y_true.append(1 if data["Close"].iloc[i+1] > data["Close"].iloc[i] else 0)

        X      = np.array(X)
        y_true = np.array(y_true)
        y_pred_raw    = model.predict(X, verbose=0).flatten()
        curr_closes   = data["Close"].values[SEQ:-1]
        y_pred        = (y_pred_raw > curr_closes).astype(int)

        total    = len(y_true)
        correct  = int(np.sum(y_pred == y_true))
        accuracy = round(correct / total * 100, 2)

        result.update({
            "status":       "ok",
            "samples":      total,
            "correct":      correct,
            "accuracy_pct": accuracy,
            "precision_up": round(np.sum((y_pred==1)&(y_true==1)) / max(np.sum(y_pred==1),1) * 100, 2),
            "recall_up":    round(np.sum((y_pred==1)&(y_true==1)) / max(np.sum(y_true==1),1) * 100, 2),
            "grade":        "PASS" if accuracy >= 55 else "REVIEW",
        })

    except ImportError:
        result["note"] = "TensorFlow not installed — pip install tensorflow==2.16.1"
    except Exception as e:
        result["status"] = "error"
        result["error"]  = str(e)

    return result


def run_evaluation():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    report = {
        "generated":  datetime.now().strftime("%d %b %Y %H:%M:%S"),
        "platform":   "NXIO v3.0.0",
        "compliance": "SEBI Algo-ID April 2026 Mandate",
        "results":    [],
    }

    print("\nNXIO — Model Evaluation Report")
    print("=" * 50)

    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            res = evaluate_model(symbol, tf)
            report["results"].append(res)
            acc   = res.get("accuracy_pct", "N/A")
            grade = res.get("grade", "")
            print(f"  {symbol:12s} {tf:4s} | {res['status']:7s} | Acc: {acc}% {grade}")

    ok = [r for r in report["results"] if r["status"] == "ok"]
    if ok:
        avg = round(sum(r["accuracy_pct"] for r in ok) / len(ok), 2)
        report["summary"] = {
            "models_evaluated": len(ok),
            "avg_accuracy_pct": avg,
            "pass":   sum(1 for r in ok if r.get("grade") == "PASS"),
            "review": sum(1 for r in ok if r.get("grade") == "REVIEW"),
        }
        print(f"\n  Avg Accuracy: {avg}%")
    else:
        report["summary"] = {"note": "TensorFlow not installed — models not evaluated"}

    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"eval_{ts}.json")
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report saved → {path}\n")
    return report


if __name__ == "__main__":
    run_evaluation()
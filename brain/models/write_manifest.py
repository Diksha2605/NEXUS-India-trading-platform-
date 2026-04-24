import os, json, hashlib
from datetime import datetime
MODELS_DIR    = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(MODELS_DIR, "manifest.json")
SYMBOLS    = ["RELIANCE", "TCS", "HDFCBANK"]
TIMEFRAMES = ["5m", "15m", "1h"]
SYM_PREFIX = {"RELIANCE": "reliance", "TCS": "tcs", "HDFCBANK": "hdfcbank"}
def file_md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()
def build_manifest():
    manifest = {
        "generated":  datetime.now().strftime("%d %b %Y %H:%M:%S"),
        "platform":   "NXIO v3.0.0",
        "compliance": "SEBI Algo-ID April 2026 Mandate",
        "models":     [],
    }
    for symbol in SYMBOLS:
        for tf in TIMEFRAMES:
            prefix = SYM_PREFIX[symbol]
            mfile  = f"lstm_{prefix}_{tf}.h5"
            sfile  = f"scaler_{prefix}_{tf}.npz"
            mpath  = os.path.join(MODELS_DIR, mfile)
            spath  = os.path.join(MODELS_DIR, sfile)
            me     = os.path.exists(mpath)
            se     = os.path.exists(spath)
            entry  = {
                "symbol": symbol, "timeframe": tf,
                "model_file": mfile, "scaler_file": sfile,
                "model_exists": me, "scaler_exists": se,
                "status": "ready" if (me and se) else "missing",
            }
            if me:
                stat = os.stat(mpath)
                entry["model_size_kb"]  = round(stat.st_size / 1024, 1)
                entry["model_modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%d %b %Y %H:%M")
                entry["model_md5"]      = file_md5(mpath)
            if se:
                entry["scaler_size_kb"] = round(os.stat(spath).st_size / 1024, 1)
            manifest["models"].append(entry)
    ready = sum(1 for m in manifest["models"] if m["status"] == "ready")
    manifest["summary"] = {"total": len(manifest["models"]), "ready": ready, "missing": len(manifest["models"]) - ready}
    return manifest
if __name__ == "__main__":
    m = build_manifest()
    with open(MANIFEST_PATH, "w") as f:
        json.dump(m, f, indent=2)
    print(f"Manifest written -> {MANIFEST_PATH}")
    print(f"Models: {m['summary']['ready']}/{m['summary']['total']} ready")

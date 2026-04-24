# NXIO — RUNBOOK.md
**Platform:** NXIO v3.0.0 | ML Algorithmic Trading Platform  
**Author:** Diksha — Founder & ML Engineer  
**Last Updated:** April 2026  
**Compliance:** SEBI Algo-ID April 2026 Mandate

---

## Quick Reference

| Service | URL | Command |
|---------|-----|---------|
| API Server | http://localhost:8000 | `python -m uvicorn api.server:app --reload --port 8000` |
| Health Check | http://localhost:8000/health | Browser or curl |
| API Docs | http://localhost:8000/docs | Browser |
| Run Tests | — | `python -m pytest` |

---

## Incident 1 — API Server Won't Start

**Symptoms:** `uvicorn` command fails, server not reachable.

**Steps:**
1. Check you are in project root:
   ```powershell
   cd C:\Users\User\Desktop\NEXUS-INDIA
   ```
2. Activate venv:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
3. Use `python -m uvicorn` (not bare `uvicorn`):
   ```powershell
   python -m uvicorn api.server:app --reload --port 8000
   ```
4. If `ModuleNotFoundError`: check the missing module and install:
   ```powershell
   pip install <module-name>
   ```
5. If port busy:
   ```powershell
   python -m uvicorn api.server:app --reload --port 8001
   ```

---

## Incident 2 — PREDICTION FAILED on All Symbols

**Symptoms:** `/predict` returns `{"error": "Prediction failed"}` for all assets.

**Root Cause Check:**
1. Was this a `minutes` vs `seconds` bug? Already fixed in Week 1 (`brain/predictor.py` line 80).
2. Check model files exist:
   ```powershell
   ls brain\models\*.h5
   ```
3. Check processed data exists:
   ```powershell
   ls data\processed\
   ```
4. Run manifest to confirm model status:
   ```powershell
   python brain\models\write_manifest.py
   ```
5. If models missing — retrain:
   ```powershell
   python brain\lstm_model.py
   ```

---

## Incident 3 — Database Corruption / Portfolio Shows Wrong Data

**Symptoms:** `/paper/portfolio` returns wrong cash, missing holdings, or 500 error.

**Steps:**
1. Check DB file exists:
   ```powershell
   ls data\nxio.db
   ```
2. Quick DB integrity check:
   ```powershell
   python -c "import sqlite3; c=sqlite3.connect('data/nxio.db'); print(c.execute('PRAGMA integrity_check').fetchone())"
   ```
   Should return `('ok',)`.
3. If corrupted — DB is WAL mode so last good state is preserved. Reset only as last resort:
   ```powershell
   # WARNING: This wipes all paper trades
   curl -X POST http://localhost:8000/paper/reset -H "X-API-Key: <your-key>"
   ```
4. Backup before reset:
   ```powershell
   copy data\nxio.db data\nxio_backup.db
   ```

---

## Incident 4 — API Returns 403 on Paper Trading Endpoints

**Symptoms:** `/paper/buy` or `/paper/sell` returns `403 Forbidden`.

**Two possible causes:**

**A) Missing API Key:**
- All paper trading endpoints require `X-API-Key` header.
- Add header to your request:
  ```
  X-API-Key: <value from .env NXIO_API_KEY>
  ```

**B) Wrong NXIO_ENV:**
- `.env` must have `NXIO_ENV=paper` or `NXIO_ENV=development`.
- Check `.env`:
  ```powershell
  type .env
  ```
- Fix and restart server.

---

## Incident 5 — GitHub Actions CI Failing

**Symptoms:** Red X on GitHub Actions after push.

**Steps:**
1. Go to repo → Actions tab → click failed run → expand failing step.
2. **Lint failure (flake8):** Fix the flagged lines, max line length is 120.
3. **Test failure:** Run locally first:
   ```powershell
   python -m pytest tests/ -v
   ```
4. **Import error in CI:** Check `requirements.txt` has all dependencies pinned.
5. **Coverage below 80%:** Add tests for uncovered lines shown in coverage report.
6. After fixing, commit and push:
   ```powershell
   git add .
   git commit -m "Fix: <describe fix>"
   git push origin main
   ```

---

## Daily Health Check (30 seconds)

```powershell
# 1. Server running?
curl http://localhost:8000/health

# 2. Tests still passing?
python -m pytest --tb=short -q

# 3. Models intact?
python brain\models\write_manifest.py
```

All green = NXIO is healthy. 🟢

---

## Emergency Contacts

| Role | Contact |
|------|---------|
| Founder & ML Engineer | Diksha |
| SEBI Compliance Ref | SEBI Algo-ID Circular April 2026 |
| Platform | PAPER TRADING ONLY — NOT SEBI REGISTERED |

---

*NXIO · Trade at the speed of signal.*  
*NOT SEBI REGISTERED · PAPER TRADING ONLY · NOT FINANCIAL ADVICE*
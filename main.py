# ============================================================
#  NEXUS INDIA — main.py
#  Usage:
#    python main.py            -> Full data collection
#    python main.py --summary  -> Show saved data
#    python main.py --stocks   -> NSE stocks only
#    python main.py --indices  -> Indices only
#    python main.py --mcx      -> MCX only
# ============================================================
import sys, os
from colorama import Fore, Style, init
from datetime import datetime
init(autoreset=True)
def print_banner():
    print(f"""
{Fore.CYAN}{'='*55}
{Fore.WHITE}  NEXUS INDIA — Multi-Timeframe Market Intelligence
{Fore.YELLOW}  NSE | BSE | MCX  |  LSTM + FII/DII + Cross-Market
{Fore.WHITE}  Phase 1: Data Collection  |  {datetime.now().strftime('%d %b %Y %H:%M')}
{Fore.CYAN}{'='*55}{Style.RESET_ALL}
""")
def create_project_structure():
    from config import (BASE_DIR, DATA_DIR, RAW_DIR, PROC_DIR,
                        LIVE_DIR, MODEL_DIR, LOG_DIR, TIMEFRAMES)
    folders = [
        DATA_DIR, PROC_DIR, LIVE_DIR, MODEL_DIR, LOG_DIR,
        os.path.join(BASE_DIR, "collectors"),
        os.path.join(BASE_DIR, "brain"),
        os.path.join(BASE_DIR, "risk"),
        os.path.join(BASE_DIR, "signals"),
        os.path.join(BASE_DIR, "api"),
        os.path.join(BASE_DIR, "dashboard"),
        os.path.join(BASE_DIR, "backtester"),
    ]
    for tf, cfg in TIMEFRAMES.items():
        folders.append(os.path.join(RAW_DIR, cfg["label"]))
    created = 0
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            print(f"{Fore.GREEN}  [+]{Style.RESET_ALL} Created: {folder}")
            created += 1
    if created:
        print(f"\n{Fore.CYAN}  {created} folders created.{Style.RESET_ALL}\n")
    else:
        print(f"{Fore.YELLOW}  All folders already exist.{Style.RESET_ALL}\n")
def main():
    print_banner()
    args = sys.argv[1:]
    print(f"{Fore.CYAN}[SETUP] Creating project structure ...{Style.RESET_ALL}")
    create_project_structure()
    if "--summary" in args:
        from collectors.nse_stocks import print_summary
        print_summary()
        return
    run_stocks  = "--stocks"  in args or len(args) == 0
    run_indices = "--indices" in args or len(args) == 0
    run_mcx     = "--mcx"     in args or len(args) == 0
    if run_stocks:
        print(f"{Fore.CYAN}\n[PHASE 1A] Collecting NSE Stocks ...{Style.RESET_ALL}")
        from collectors.nse_stocks import fetch_all_stocks
        fetch_all_stocks(save=True)
    if run_indices:
        print(f"{Fore.CYAN}\n[PHASE 1B] Collecting Indices ...{Style.RESET_ALL}")
        from collectors.nifty import fetch_all_indices
        fetch_all_indices(save=True)
    if run_mcx:
        print(f"{Fore.CYAN}\n[PHASE 1C] Collecting MCX Commodities ...{Style.RESET_ALL}")
        from collectors.mcx import fetch_all_mcx
        fetch_all_mcx(save=True)
    print(f"\n{Fore.CYAN}[SUMMARY]{Style.RESET_ALL}")
    from collectors.nse_stocks import print_summary
    print_summary()
    print(f"""{Fore.GREEN}
{'='*55}
  PHASE 1 COMPLETE
  Data saved in: data/raw/
  Next: python brain/features.py
{'='*55}{Style.RESET_ALL}
""")
if __name__ == "__main__":
    main()

import MetaTrader5 as mt5

# --- FILL IN YOUR MASTER DETAILS HERE ---
MASTER_PATH = "C:/Program Files/MetaTrader 5/terminal64.exe"
MASTER_LOGIN = 5053307347
MASTER_PASS = "-5QaHrVs"
MASTER_SERVER = "MetaQuotes-Demo"

print("--- DIAGNOSTIC TEST ---")
print(f"Testing path: {MASTER_PATH}")

# 1. Test basic initialization
if not mt5.initialize(path=MASTER_PATH):
    print(f"[X] FAIL: Failed to launch terminal path. Error: {mt5.last_error()}")
else:
    print("[✓] SUCCESS: Terminal launched via executable path.")

    # 2. Test account login
    authorized = mt5.login(login=MASTER_LOGIN, password=MASTER_PASS, server=MASTER_SERVER)
    if authorized:
        acc_info = mt5.account_info()
        print(f"[✓] SUCCESS: Logged in! Account Balance: ${acc_info.balance}")
    else:
        print(f"[X] FAIL: Account login failed. Error: {mt5.last_error()}")

mt5.shutdown()
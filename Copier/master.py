import MetaTrader5 as mt5
import time
import sys

# --- CONFIGURATION ---
ACCOUNTS = [
    {
        "role": "Master",
        "login": 5053307347,
        "pass": "-5QaHrVs",
        "server": "MetaQuotes-Demo",
        "path": r"C:/Program Files/MetaTrader 5/terminal64.exe"
    },
    {
        "role": "Slave 1",
        "login": 109933448,
        "pass": "-yUd2uQv",
        "server": "MetaQuotes-Demo",
        "path": r"C:/Program Files/MetaTrader 5 Slave 1/terminal64.exe"
    },
    {
        "role": "Slave 2",
        "login": 109933471,
        "pass": "Jz-hWc4p",
        "server": "MetaQuotes-Demo",
        "path": r"C:/Program Files/MetaTrader 5 Slave 2/terminal64.exe"
    },
    {
        "role": "Slave 3",
        "login": 109933494,
        "pass": "XkX*6yKs",
        "server": "MetaQuotes-Demo",
        "path": r"C:/Program Files/MetaTrader 5 Slave 3/terminal64.exe"
    }
]

MAGIC_NUMBER = 999111
ticket_map = {}  # { master_ticket: { "symbol": ..., "volume": ..., "type": ..., "slaves": { slave_idx: slave_ticket } } }

def initialize_terminals():
    """Initializes and logs into all MT5 terminals simultaneously without closing them."""
    for i, acc in enumerate(ACCOUNTS):
        print(f"[*] Connecting to {acc['role']} ({acc['login']})...")
        
        # Initialize specific terminal instance
        if not mt5.initialize(path=acc["path"], login=acc["login"], password=acc["pass"], server=acc["server"], timeout=10000):
            print(f"[X] Failed to initialize {acc['role']}: {mt5.last_error()}")
            return False
            
        print(f"[✓] Successfully connected to {acc['role']}")
    return True

def ensure_symbol_ready(symbol):
    """Ensures a symbol is selected and visible in the active terminal's Market Watch."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"[!] Symbol {symbol} not found.")
        return False
        
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            print(f"[!] Failed to select symbol {symbol} in Market Watch.")
            return False
    return True

def get_current_price(symbol, order_type):
    """Retrieves Ask or Bid price safely."""
    if not ensure_symbol_ready(symbol):
        return None
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    return tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

def open_slave_trade(acc_index, symbol, volume, order_type, master_ticket):
    """Switches context to the specified slave terminal and opens a copy trade dynamically."""
    acc = ACCOUNTS[acc_index]
    
    # Select the target slave terminal context
    if not mt5.initialize(path=acc["path"], login=acc["login"], password=acc["pass"], server=acc["server"]):
        print(f"[X] Context switch failed for {acc['role']}")
        return None

    price = get_current_price(symbol, order_type)
    if price is None:
        print(f"[!] Price unavailable for {symbol} on {acc['role']}")
        return None

    # --- AUTO-DETECT SUPPORTED FILLING MODE ---
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"[!] Symbol {symbol} info not found on {acc['role']}")
        return None

    filling_type = mt5.ORDER_FILLING_IOC # Default fallback
    
    # Check what filling modes the broker supports for this symbol
    # filling_mode flags: 1 = FOK, 2 = IOC, 4 = RETURN
    if symbol_info.filling_mode & 2:  # IOC supported
        filling_type = mt5.ORDER_FILLING_IOC
    elif symbol_info.filling_mode & 1: # FOK supported
        filling_type = mt5.ORDER_FILLING_FOK
    elif symbol_info.filling_mode & 4: # RETURN supported
        filling_type = mt5.ORDER_FILLING_RETURN

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": f"Copy M:{master_ticket}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling_type,  # Uses the dynamically detected filling mode
    }

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"[✓] Copied to {acc['role']} successfully (Ticket: {result.order})")
        return result.order
    else:
        err = result.comment if result else mt5.last_error()
        print(f"[X] Failed to copy to {acc['role']}: {err}")
        return None

def close_slave_trade(acc_index, symbol, volume, master_order_type, slave_ticket):
    """Switches context to the specified slave terminal and closes the position."""
    acc = ACCOUNTS[acc_index]
    
    if not mt5.initialize(path=acc["path"], login=acc["login"], password=acc["pass"], server=acc["server"]):
        print(f"[X] Context switch failed for {acc['role']}")
        return False

    close_type = mt5.ORDER_TYPE_SELL if master_order_type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = get_current_price(symbol, close_type)

    if price is None:
        return False

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(volume),
        "type": close_type,
        "position": slave_ticket,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "Copy CLOSE",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"[✓] Closed position on {acc['role']} (Ticket: {slave_ticket})")
        return True
    else:
        err = result.comment if result else mt5.last_error()
        print(f"[X] Failed to close on {acc['role']}: {err}")
        return False

# --- MAIN EXECUTION ENGINE ---
print("==========================================")
print("   Robust MT5 Trade Copier Engine        ")
print("==========================================")

if not initialize_terminals():
    print("[!] Initialization failed. Exiting.")
    sys.exit(1)

print("\n[✓] All accounts connected. Monitoring Master account...\n")

while True:
    try:
        # 1. Focus on Master Account Context
        master_acc = ACCOUNTS[0]
        if not mt5.initialize(path=master_acc["path"], login=master_acc["login"], password=master_acc["pass"], server=master_acc["server"]):
            print("[!] Lost connection to Master terminal. Retrying...")
            time.sleep(1)
            continue

        master_positions = mt5.positions_get()
        master_tickets = {p.ticket: p for p in master_positions} if master_positions else {}

        # 2. SYNC OPEN TRADES
        for m_ticket, pos in master_tickets.items():
            if m_ticket not in ticket_map:
                print(f"\n[!] New Master Trade Found -> Ticket: {m_ticket} | Symbol: {pos.symbol} | Type: {'BUY' if pos.type == 0 else 'SELL'} | Vol: {pos.volume}")
                
                copied_slave_tickets = {}
                for slave_idx in range(1, len(ACCOUNTS)):
                    s_ticket = open_slave_trade(slave_idx, pos.symbol, pos.volume, pos.type, m_ticket)
                    if s_ticket:
                        copied_slave_tickets[slave_idx] = s_ticket

                ticket_map[m_ticket] = {
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": pos.type,
                    "slaves": copied_slave_tickets
                }

        # 3. SYNC CLOSED TRADES
        # 3. SYNC CLOSED TRADES: Detect positions closed on Master
        closed_masters = [t for t in ticket_map if t not in master_tickets]
        for m_ticket in closed_masters:
            trade_data = ticket_map[m_ticket]
            print(f"\n[!] Master Trade Closed -> Ticket: {m_ticket}")

            for slave_idx, slave_ticket in trade_data["slaves"].items():
                close_slave_trade(
                    acc_index=slave_idx,
                    symbol=trade_data["symbol"],
                    volume=trade_data["volume"],
                    master_order_type=trade_data["type"],
                    slave_ticket=slave_ticket
                )

            del ticket_map[m_ticket]

        time.sleep(0.3)  # Balanced polling rate to prevent CPU spikes

    except KeyboardInterrupt:
        print("\n[!] Copier stopped by user. Shutting down...")
        mt5.shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"[!] Error encountered in main loop: {e}")
        time.sleep(1)
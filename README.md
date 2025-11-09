# Ledge

A **local, private, native-GUI** crypto transaction ledger for **Canadian ACB (Adjusted Cost Base)** tracking.

- Tracks buys, sells, trades, staking, fees, and gas
- Compliant with CRA guidance
- Saves to SQLite (no CSV fragility)
- No internet required
- Built with Python + Tkinter

🪶 What v1.2 Delivers
- Accurate Canadian ACB (buys, sells, trades, staking)
- Fee handling (exchange + gas)
- Native GUI with centered, responsive dialogs
- Context-aware labels (no more “Received Token” on sells!)
- Input validation (no crashes, clear errors)
- Rich reporting (per-token gains, holdings, fees, activity)
- CSV export (for your records or accountant)
- Keyboard shortcuts (Enter/Esc — because you deserve speed)
- 100% local, private, and yours

## Requirements
- Python 3.7+
- `tkinter` (usually built-in)

## Run
```bash
python3 ledge.py
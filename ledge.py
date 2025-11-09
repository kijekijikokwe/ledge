# crypto_acb_gui.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
import configparser
import os
import csv
from datetime import datetime
from collections import defaultdict

DB_FILE = "ledge.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        token TEXT NOT NULL,
        action TEXT NOT NULL,
        token_amount REAL NOT NULL,
        cad_amount REAL NOT NULL,
        notes TEXT,
        sent_token TEXT,
        sent_amount REAL,
        sent_cad REAL,
        fee_cad REAL DEFAULT 0.0,    -- exchange fee
        gas_cad REAL DEFAULT 0.0     -- network fee
    )
    ''')
    conn.execute('''
    CREATE TABLE IF NOT EXISTS acb_state (
        token TEXT PRIMARY KEY,
        total_acb REAL NOT NULL DEFAULT 0.0,
        units_held REAL NOT NULL DEFAULT 0.0
    )
    ''')
    conn.commit()
    conn.close()

class TransactionDialog(tk.Toplevel):
    def __init__(self, parent, transaction=None):
        super().__init__(parent)
        self.title("Add Transaction" if not transaction else "Edit Transaction")
        self.result = None
        self.transient(parent)
        self.grab_set()

        self.label_map = {
            "Buy": ("Token:", "Amount:", "CAD Value:"),
            "Sell": ("Token:", "Amount Sold:", "Proceeds (CAD):"),
            "Trade": ("Received Token:", "Received Amount:", "Received CAD:"),
            "StakeIn": ("Token:", "Amount Staked:", "CAD Value:"),
            "StakeOut": ("Token:", "Amount Unstaked:", "CAD Value:"),
            "Reward": ("Token:", "Amount:", "FMV (CAD):")
        }

        # Center dialog over parent
        self.update_idletasks()  # Ensure geometry is calculated
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = self.winfo_reqwidth()
        dialog_height = self.winfo_reqheight()
        x = parent_x + (parent_width // 2) - (dialog_width // 2)
        y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"+{x}+{y}")

        # Start row counter
        row = 0

        # Date
        tk.Label(self, text="Date (YYYY-MM-DD):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=transaction[1] if transaction else datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(self, textvariable=self.date_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Action
        tk.Label(self, text="Action:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.action_var = tk.StringVar(value=transaction[3] if transaction else "Buy")
        actions = ["Buy", "Sell", "Trade", "StakeIn", "StakeOut", "Reward"]
        self.action_cb = ttk.Combobox(self, textvariable=self.action_var, values=actions, state="readonly", width=10)
        self.action_cb.grid(row=row, column=1, padx=5, pady=5)
        self.action_cb.bind("<<ComboboxSelected>>", self.on_action_change)
        row += 1

        # Dynamic labels
        self.token_lbl = tk.Label(self, text="Token:")
        self.token_lbl.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.token_var = tk.StringVar(value=transaction[2] if transaction else "")
        tk.Entry(self, textvariable=self.token_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        self.amount_lbl = tk.Label(self, text="Amount:")
        self.amount_lbl.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.token_amt_var = tk.DoubleVar(value=transaction[4] if transaction else 0.0)
        tk.Entry(self, textvariable=self.token_amt_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        self.cad_lbl = tk.Label(self, text="CAD Value:")
        self.cad_lbl.grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.cad_amt_var = tk.DoubleVar(value=transaction[5] if transaction else 0.0)
        tk.Entry(self, textvariable=self.cad_amt_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Trade fields (initially hidden)
        self.sent_token_lbl = tk.Label(self, text="Sent Token:")
        self.sent_token_var = tk.StringVar(value=transaction[7] if transaction and len(transaction) > 7 else "")
        self.sent_token_ent = tk.Entry(self, textvariable=self.sent_token_var, width=12)

        self.sent_amt_lbl = tk.Label(self, text="Sent Amount:")
        self.sent_amt_var = tk.DoubleVar(value=transaction[8] if transaction and len(transaction) > 8 else 0.0)
        self.sent_amt_ent = tk.Entry(self, textvariable=self.sent_amt_var, width=12)

        self.sent_cad_lbl = tk.Label(self, text="Sent CAD Value:")
        self.sent_cad_var = tk.DoubleVar(value=transaction[9] if transaction and len(transaction) > 9 else 0.0)
        self.sent_cad_ent = tk.Entry(self, textvariable=self.sent_cad_var, width=12)

        self.sent_widgets = [
            (self.sent_token_lbl, self.sent_token_ent),
            (self.sent_amt_lbl, self.sent_amt_ent),
            (self.sent_cad_lbl, self.sent_cad_ent)
        ]

        # Fee fields (always shown)
        tk.Label(self, text="Exchange Fee (CAD):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.fee_cad_var = tk.DoubleVar(value=transaction[10] if transaction and len(transaction) > 10 else 0.0)
        tk.Entry(self, textvariable=self.fee_cad_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        tk.Label(self, text="Gas/Network Fee (CAD):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.gas_cad_var = tk.DoubleVar(value=transaction[11] if transaction and len(transaction) > 11 else 0.0)
        tk.Entry(self, textvariable=self.gas_cad_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Notes
        tk.Label(self, text="Notes:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.notes_var = tk.StringVar(value=transaction[6] if transaction else "")
        tk.Entry(self, textvariable=self.notes_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1

        # Save row for trade fields
        self.trade_start_row = row

        # Buttons
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        self.ok_btn = tk.Button(btn_frame, text="OK", command=self.on_ok, default=tk.ACTIVE)
        self.ok_btn.pack(side=tk.LEFT, padx=5)
        self.bind('<Return>', lambda event: self.ok_btn.invoke())
        self.bind('<Escape>', lambda event: self.destroy())
        tk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

        # Trigger initial layout
        self.on_action_change()
        self.wait_window(self)

        # Set focus to first entry field
        self.after(50, self.focus_first_entry)

    def focus_first_entry(self):
        try:
            for child in self.winfo_children():
                if isinstance(child, tk.Frame):
                    for grandchild in child.winfo_children():
                        if isinstance(grandchild, tk.Entry):
                            grandchild.focus()
                            return
                elif isinstance(child, tk.Entry):
                    child.focus()
                    return
        except tk.TclError:
            # Dialog was destroyed before focus could be set — safe to ignore
            pass

    def on_action_change(self, event=None):
        action = self.action_var.get()
        
        # Update main labels
        token_text, amount_text, cad_text = self.label_map.get(action, ("Token:", "Amount:", "CAD Value:"))
        self.token_lbl.config(text=token_text)
        self.amount_lbl.config(text=amount_text)
        self.cad_lbl.config(text=cad_text)

        # Show/hide trade fields
        for lbl, ent in self.sent_widgets:
            lbl.grid_forget()
            ent.grid_forget()

        if action == "Trade":
            current_row = self.trade_start_row
            for lbl, ent in self.sent_widgets:
                lbl.grid(row=current_row, column=0, sticky=tk.W, padx=5, pady=5)
                ent.grid(row=current_row, column=1, padx=5, pady=5)
                current_row += 1
            btn_frame = self.children['!frame']
            btn_frame.grid(row=current_row, column=0, columnspan=2, pady=10)
        else:
            btn_frame = self.children['!frame']
            btn_frame.grid(row=self.trade_start_row, column=0, columnspan=2, pady=10)

    def on_ok(self):
        try:
            # Validate date
            datetime.strptime(self.date_var.get(), "%Y-%m-%d")
            
            action = self.action_var.get()
            token = self.token_var.get().strip()
            token_amount = float(self.token_amt_var.get())
            cad_amount = float(self.cad_amt_var.get())

            # --- Common validations (all actions) ---
            if not token:
                messagebox.showerror("Input Error", "Token cannot be empty")
                return
            if token_amount <= 0:
                messagebox.showerror("Input Error", "Amount must be greater than 0")
                return
            if cad_amount < 0:
                messagebox.showerror("Input Error", "CAD value cannot be negative")
                return

            # --- Trade-specific validations ---
            if action == "Trade":
                sent_token = self.sent_token_var.get().strip()
                try:
                    sent_amount = float(self.sent_amt_var.get())
                    sent_cad = float(self.sent_cad_var.get())
                except ValueError:
                    messagebox.showerror("Input Error", "Sent amount and CAD must be valid numbers")
                    return

                if not sent_token:
                    messagebox.showerror("Input Error", "Sent Token cannot be empty for a Trade")
                    return
                if sent_amount <= 0:
                    messagebox.showerror("Input Error", "Sent Amount must be greater than 0")
                    return
                if sent_cad < 0:
                    messagebox.showerror("Input Error", "Sent CAD cannot be negative")
                    return

                # Store for result
                sent_token_val = sent_token
                sent_amount_val = sent_amount
                sent_cad_val = sent_cad

            else:
                # Non-Trade: sent fields are None
                sent_token_val = None
                sent_amount_val = None
                sent_cad_val = None

            # --- Fee validations (all actions) ---
            try:
                fee_cad = float(self.fee_cad_var.get() or 0.0)
                gas_cad = float(self.gas_cad_var.get() or 0.0)
                if fee_cad < 0 or gas_cad < 0:
                    messagebox.showerror("Input Error", "Fees cannot be negative")
                    return
            except ValueError:
                messagebox.showerror("Input Error", "Fee and gas must be valid numbers")
                return

            # Build result tuple (11 values)
            self.result = (
                self.date_var.get(),
                token,
                action,
                token_amount,
                cad_amount,
                self.notes_var.get(),
                sent_token_val,
                sent_amount_val,
                sent_cad_val,
                fee_cad,
                gas_cad
            )
            self.destroy()

        except Exception as e:
            messagebox.showerror("Input Error", f"Invalid input:\n{e}")

class CryptoACBApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ledge")
        # Load geometry before setting up UI
        self.load_geometry()
        # Save geometry when window is closed
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        init_db()
        self.setup_ui()
        self.load_data()

    def load_geometry(self):
        """Load window geometry from ledge.ini, or use default"""
        config = configparser.ConfigParser()
        if os.path.exists('ledge.ini'):
            try:
                config.read('ledge.ini')
                geom = config.get('window', 'geometry', fallback='950x600+100+100')
                self.root.geometry(geom)
            except:
                self.root.geometry('950x600+100+100')
        else:
            self.root.geometry('950x600+100+100')
    
    def on_closing(self):
        self.save_geometry()
        self.root.destroy()

    def setup_ui(self):
        # Notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Transactions
        # Tab 1: Transactions
        self.trans_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.trans_frame, text="Transactions")

        trans_btn_frame = ttk.Frame(self.trans_frame)
        trans_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(trans_btn_frame, text="Add", command=self.add_transaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(trans_btn_frame, text="Edit", command=self.edit_transaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(trans_btn_frame, text="Delete", command=self.delete_transaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(trans_btn_frame, text="Recalculate ACB", command=self.recompute_acb).pack(side=tk.RIGHT, padx=5)
        ttk.Button(trans_btn_frame, text="Export CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=5)

        # Updated columns: include sent_* for trades
        cols = ("ID", "Date", "Action", "ReceivedToken", "ReceivedAmt", "ReceivedCAD",
                "SentToken", "SentAmt", "SentCAD", "FeeCAD", "GasCAD","Notes")
        self.trans_tree = ttk.Treeview(self.trans_frame, columns=cols, show="headings", height=15)
        col_widths = {
            "ID": 40, "Date": 100, "Action": 80,
            "ReceivedToken": 90, "ReceivedAmt": 90, "ReceivedCAD": 90,
            "SentToken": 90, "SentAmt": 90, "SentCAD": 90,
            "Notes": 200
        }
        for col in cols:
            self.trans_tree.heading(col, text=col.replace("Received", "Rec.").replace("Sent", "Sent"))
            self.trans_tree.column(col, width=col_widths.get(col, 100))
        self.trans_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        vscroll = ttk.Scrollbar(self.trans_tree, orient="vertical", command=self.trans_tree.yview)
        self.trans_tree.configure(yscroll=vscroll.set)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Tab 2: ACB Summary
        self.acb_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.acb_frame, text="ACB Summary")

        acb_cols = ("Token", "UnitsHeld", "TotalACB", "ACBperUnit")
        self.acb_tree = ttk.Treeview(self.acb_frame, columns=acb_cols, show="headings", height=15)
        for col in acb_cols:
            self.acb_tree.heading(col, text=col)
            self.acb_tree.column(col, width=150)
        self.acb_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Tab 3: Reports
        self.report_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.report_frame, text="Reports")

        self.report_text = tk.Text(self.report_frame, wrap=tk.WORD, padx=10, pady=10)
        self.report_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_report()

    def load_data(self):
        self.load_transactions()
        self.load_acb_summary()

    def load_transactions(self):
        for item in self.trans_tree.get_children():
            self.trans_tree.delete(item)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute("""
                SELECT id, date, action, token, token_amount, cad_amount,
                       sent_token, sent_amount, sent_cad, fee_cad, gas_cad, notes
                FROM transactions
                ORDER BY date, id
            """)
            for row in cur.fetchall():
                # Format numbers
                fmt_row = (
                    row[0],  # ID
                    row[1],  # Date
                    row[2],  # Action
                    row[3] or "",  # Received Token
                    f"{row[4]:.8f}" if row[4] is not None else "",  # Received Amt
                    f"${row[5]:.2f}" if row[5] is not None else "",  # Received CAD
                    row[6] or "",  # Sent Token
                    f"{row[7]:.8f}" if row[7] is not None else "",  # Sent Amt
                    f"${row[8]:.2f}" if row[8] is not None else "",  # Sent CAD
                    f"${row[9]:.2f}" if row[9] is not None else "",   # FeeCAD
                    f"${row[10]:.2f}" if row[10] is not None else "", # GasCAD
                    row[11] or ""   # Notes
                )
                self.trans_tree.insert("", "end", values=fmt_row)

    def load_acb_summary(self):
        for item in self.acb_tree.get_children():
            self.acb_tree.delete(item)
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute("SELECT token, units_held, total_acb FROM acb_state ORDER BY token")
            for token, units, total in cur.fetchall():
                acb_per = total / units if units > 0 else 0.0
                self.acb_tree.insert("", "end", values=(token, f"{units:.8f}", f"${total:.2f}", f"${acb_per:.4f}"))

    def add_transaction(self):
        dialog = TransactionDialog(self.root)
        if dialog.result:
            # Unpack ALL 11 values from the dialog
            (date, token, action, token_amt, cad_amt, notes,
             sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = dialog.result

            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("""
                    INSERT INTO transactions 
                    (date, token, action, token_amount, cad_amount, notes,
                     sent_token, sent_amount, sent_cad, fee_cad, gas_cad)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (date, token, action, token_amt, cad_amt, notes,
                      sent_token, sent_amt, sent_cad, fee_cad, gas_cad))
            self.load_data()
            self.recompute_acb()
            
    def save_geometry(self):
        """Save window geometry to ledge.ini"""
        config = configparser.ConfigParser()
        config['window'] = {'geometry': self.root.geometry()}
        with open('ledge.ini', 'w') as f:
            config.write(f)

    def edit_transaction(self):
        selected = self.trans_tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Please select a transaction to edit.")
            return
        item = self.trans_tree.item(selected[0])
        values = item['values']
        # Map: ID, Date, Action, RecToken, RecAmt, RecCAD, SentToken, SentAmt, SentCAD, Notes
        trans_id = values[0]

        # Reconstruct raw values (remove formatting)
        try:
            rec_amt = float(values[4]) if values[4] else 0.0
            rec_cad = float(values[5].replace('$','')) if values[5] else 0.0
            sent_amt = float(values[7]) if values[7] else 0.0
            sent_cad = float(values[8].replace('$','')) if values[8] else 0.0
        except:
            rec_amt = rec_cad = sent_amt = sent_cad = 0.0

        old_row = (
            None,  # placeholder for ID (not used in dialog)
            values[1],  # date
            values[3],  # token (received)
            values[2],  # action
            rec_amt,    # token_amount (received)
            rec_cad,    # cad_amount (received)
            values[9],  # notes
            values[6],  # sent_token
            sent_amt,   # sent_amount
            sent_cad    # sent_cad
        )

        dialog = TransactionDialog(self.root, old_row)
        if dialog.result:
            # dialog.result = (date, token, action, token_amt, cad_amt, notes, sent_token, sent_amt, sent_cad)
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute('''
                    UPDATE transactions
                    SET date=?, token=?, action=?, token_amount=?, cad_amount=?, notes=?,
                        sent_token=?, sent_amount=?, sent_cad=?, fee_cad=?, gas_cad=?
                    WHERE id=?
                ''', (date, token, action, token_amt, cad_amt, notes,
                    sent_token, sent_amt, sent_cad, fee_cad, gas_cad, trans_id))
            self.load_data()
            self.recompute_acb()

    def delete_transaction(self):
        selected = self.trans_tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Please select a transaction to delete.")
            return
        trans_id = self.trans_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", "Delete this transaction? ACB will be recalculated."):
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute("DELETE FROM transactions WHERE id=?", (trans_id,))
            self.load_data()
            self.recompute_acb()

    def recompute_acb(self):
        with sqlite3.connect(DB_FILE) as conn:
            conn.execute("DELETE FROM acb_state")
            cur = conn.execute("""
                SELECT date, token, action, token_amount, cad_amount,
                       sent_token, sent_amount, sent_cad,
                       fee_cad, gas_cad
                FROM transactions
                ORDER BY date, id
            """)
            acb_state = defaultdict(lambda: {"total_acb": 0.0, "units_held": 0.0})

            for row in cur.fetchall():
                (date, token, action, token_amt, cad_amt,
                 sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = row

                # Handle gas fee first: always a capital loss
                if gas_cad and gas_cad > 0:
                    # Track gas fees as negative ACB in a virtual "GAS_FEES" token
                    acb_state["GAS_FEES"]["total_acb"] -= gas_cad
                    # No units — just a running loss

                if action == "Buy":
                    # ACB = what you paid + fees
                    total_cost = cad_amt + (fee_cad or 0.0)
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt

                elif action == "Sell":
                    # Proceeds = what you got - fees
                    net_proceeds = cad_amt - (fee_cad or 0.0)
                    state = acb_state[token]
                    if state["units_held"] <= 0:
                        # No ACB → full gain = net_proceeds
                        pass
                    else:
                        acb_per = state["total_acb"] / state["units_held"]
                        cost_basis = acb_per * token_amt
                        state["total_acb"] = max(0.0, state["total_acb"] - cost_basis)
                        state["units_held"] = max(0.0, state["units_held"] - token_amt)

                elif action == "Trade":
                    # Sell sent_token (use sent_cad - no fee on sent side for now)
                    if sent_token and sent_amt and sent_cad is not None:
                        sent_state = acb_state[sent_token]
                        if sent_state["units_held"] > 0:
                            acb_per_sent = sent_state["total_acb"] / sent_state["units_held"]
                            cost_basis = acb_per_sent * sent_amt
                            sent_state["total_acb"] = max(0.0, sent_state["total_acb"] - cost_basis)
                            sent_state["units_held"] = max(0.0, sent_state["units_held"] - sent_amt)

                    # Buy received token: ACB = cad_amt + fee_cad
                    total_cost = cad_amt + (fee_cad or 0.0)
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt

                elif action == "Reward":
                    # ACB = FMV at time of receipt (fees don't apply here)
                    acb_state[token]["total_acb"] += cad_amt
                    acb_state[token]["units_held"] += token_amt

                elif action in ("StakeIn", "StakeOut"):
                    state = acb_state[token]
                    if action == "StakeIn":
                        state["units_held"] = max(0.0, state["units_held"] - token_amt)
                    else:
                        state["units_held"] += token_amt

            # Save all states (including GAS_FEES)
            for token, state in acb_state.items():
                conn.execute(
                    "INSERT OR REPLACE INTO acb_state (token, total_acb, units_held) VALUES (?, ?, ?)",
                    (token, state["total_acb"], state["units_held"])
                )
        self.load_acb_summary()

    def generate_report_data(self):
        with sqlite3.connect(DB_FILE) as conn:
            cur = conn.execute("""
                SELECT date, token, action, token_amount, cad_amount,
                       sent_token, sent_amount, sent_cad,
                       fee_cad, gas_cad
                FROM transactions
                ORDER BY date, id
            """)
            acb_state = defaultdict(lambda: {"total_acb": 0.0, "units_held": 0.0})
            total_realized_gain = 0.0
            total_gas_loss = 0.0
            total_exchange_fees = 0.0
            action_counts = defaultdict(int)
            
            # Track per-token gains/losses
            token_gains = defaultdict(float)
            token_gas = defaultdict(float)

            for row in cur.fetchall():
                (date, token, action, token_amt, cad_amt,
                 sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = row

                action_counts[action] += 1
                fee_cad = fee_cad or 0.0
                gas_cad = gas_cad or 0.0

                # Accumulate totals
                total_exchange_fees += fee_cad
                total_gas_loss += gas_cad
                if gas_cad > 0:
                    token_gas[token] += gas_cad
                    if sent_token:
                        token_gas[sent_token] += gas_cad  # or assign to primary token

                if action == "Buy":
                    total_cost = cad_amt + fee_cad
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt

                elif action == "Sell":
                    net_proceeds = cad_amt - fee_cad
                    state = acb_state[token]
                    if state["units_held"] <= 0:
                        realized_gain = net_proceeds
                    else:
                        acb_per = state["total_acb"] / state["units_held"]
                        cost_basis = acb_per * token_amt
                        realized_gain = net_proceeds - cost_basis
                        state["total_acb"] = max(0.0, state["total_acb"] - cost_basis)
                        state["units_held"] = max(0.0, state["units_held"] - token_amt)
                    total_realized_gain += realized_gain
                    token_gains[token] += realized_gain

                elif action == "Trade":
                    # Sent token (sell)
                    if sent_token and sent_amt and sent_cad is not None:
                        sent_state = acb_state[sent_token]
                        if sent_state["units_held"] <= 0:
                            realized_gain_sent = sent_cad
                        else:
                            acb_per_sent = sent_state["total_acb"] / sent_state["units_held"]
                            cost_basis_sent = acb_per_sent * sent_amt
                            realized_gain_sent = sent_cad - cost_basis_sent
                            sent_state["total_acb"] = max(0.0, sent_state["total_acb"] - cost_basis_sent)
                            sent_state["units_held"] = max(0.0, sent_state["units_held"] - sent_amt)
                        total_realized_gain += realized_gain_sent
                        token_gains[sent_token] += realized_gain_sent

                    # Received token (buy)
                    total_cost = cad_amt + fee_cad
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt

            # Build current holdings
            current_holdings = {}
            for token, state in acb_state.items():
                if state["units_held"] > 0:
                    current_holdings[token] = {
                        "units": state["units_held"],
                        "total_acb": state["total_acb"],
                        "acb_per_unit": state["total_acb"] / state["units_held"]
                    }

            return {
                "total_realized_gain": total_realized_gain,
                "total_gas_loss": total_gas_loss,
                "total_exchange_fees": total_exchange_fees,
                "net_pnl": total_realized_gain - total_gas_loss,
                "action_counts": dict(action_counts),
                "token_gains": dict(token_gains),
                "token_gas": dict(token_gas),
                "current_holdings": current_holdings
            }

    def update_report(self):
        data = self.generate_report_data()
        report = "📊 Ledge Tax & Portfolio Summary\n"
        report += "=" * 40 + "\n\n"

        # --- Financial Totals ---
        report += "💰 Financial Summary\n"
        report += f"Total Realized Capital Gains: ${data['total_realized_gain']:.2f}\n"
        report += f"Total Gas Fees (Capital Losses): -${data['total_gas_loss']:.2f}\n"
        report += f"Total Exchange Fees Paid: ${data['total_exchange_fees']:.2f}\n"
        report += f"Net PnL (Gains - Gas Losses): ${data['net_pnl']:.2f}\n\n"

        # --- Activity ---
        report += "📈 Activity Summary\n"
        for action, count in sorted(data['action_counts'].items()):
            report += f"{action}: {count} transaction(s)\n"
        report += "\n"

        # --- Per-Token Gains ---
        if data['token_gains']:
            report += "🔖 Realized Gains by Token\n"
            for token, gain in sorted(data['token_gains'].items(), key=lambda x: -x[1]):
                report += f"{token}: ${gain:.2f}\n"
            report += "\n"

        # --- Current Holdings ---
        if data['current_holdings']:
            report += "💼 Current Holdings\n"
            for token, h in sorted(data['current_holdings'].items()):
                report += f"{token}: {h['units']:.8f} units @ ${h['acb_per_unit']:.4f}/unit (ACB: ${h['total_acb']:.2f})\n"
            report += "\n"

        # --- Gas by Token ---
        if data['token_gas']:
            report += "⛽ Gas Fees by Token\n"
            for token, gas in sorted(data['token_gas'].items(), key=lambda x: -x[1]):
                report += f"{token}: -${gas:.2f}\n"
            report += "\n"

        report += "ℹ️ Note: Unrealized gains not included in PnL.\n"
        report += "ℹ️ Use 'Export CSV' for full audit trail."

        self.report_text.delete(1.0, tk.END)
        self.report_text.insert(tk.END, report)

    def export_csv(self):
        """Export all transactions to a CSV file."""
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Save Transaction Report"
        )
        if not path:
            return

        try:
            with sqlite3.connect(DB_FILE) as conn, open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header
                writer.writerow([
                    "Date", "Action", "Received Token", "Received Amount", "Received CAD",
                    "Sent Token", "Sent Amount", "Sent CAD",
                    "Exchange Fee (CAD)", "Gas Fee (CAD)", "Notes"
                ])
                # Data
                cur = conn.execute("""
                    SELECT date, action, token, token_amount, cad_amount,
                           sent_token, sent_amount, sent_cad, fee_cad, gas_cad, notes
                    FROM transactions
                    ORDER BY date, id
                """)
                for row in cur.fetchall():
                    writer.writerow(row)
            messagebox.showinfo("Export", f"Transactions exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export CSV:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = CryptoACBApp(root)
    root.mainloop()
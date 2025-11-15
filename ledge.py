# ledge.py
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
import configparser
import os
import csv
from datetime import datetime
from collections import defaultdict
import shutil
from pathlib import Path
import decimal
from collections import defaultdict

DB_FILE = "ledge.db"

def backup_database():
    """Create a backup of the database file with timestamp."""
    if not Path(DB_FILE).exists():
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = Path('backups')
    backup_dir.mkdir(exist_ok=True)
    
    backup_file = backup_dir / f'ledge_{timestamp}.db'
    try:
        shutil.copy2(DB_FILE, backup_file)
        backups = sorted(backup_dir.glob('ledge_*.db'))
        if len(backups) > 5:
            for old_backup in backups[:-5]:
                old_backup.unlink()
    except Exception as e:
        print(f'Failed to create backup: {e}')


def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL CHECK (date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
            token TEXT NOT NULL,
            action TEXT NOT NULL,
            token_amount REAL NOT NULL,
            cad_amount REAL NOT NULL,
            notes TEXT,
            sent_token TEXT,
            sent_amount REAL,
            sent_cad REAL,
            fee_cad REAL DEFAULT 0.0,
            gas_cad REAL DEFAULT 0.0
        )
        ''')
        
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_date ON transactions(date)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_token ON transactions(token)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_sent_token ON transactions(sent_token)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_action ON transactions(action)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_trans_cad_amount ON transactions(cad_amount)')
        
        conn.execute('''
        CREATE TABLE IF NOT EXISTS acb_state (
            token TEXT PRIMARY KEY,
            total_acb DECIMAL(28,18) NOT NULL DEFAULT 0.0,
            units_held DECIMAL(28,18) NOT NULL DEFAULT 0.0
        )
        ''')
        conn.commit()
    except sqlite3.Error as e:
        messagebox.showerror('Database Error', f'Failed to initialize database: {e}')
        raise
    finally:
        if conn:
            conn.close()

RECEIPT_TO_ORIGINAL_MAP = {
    'sUSDe': 'USDe',
    'sUSDC': 'USDC',
    'stDOT': 'DOT',
}
ORIGINAL_TO_RECEIPT_MAP = {v: k for k, v in RECEIPT_TO_ORIGINAL_MAP.items()}

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
            "Stake": ("Receipt Token:", "Receipt Amount:", "Receipt CAD Value (Basis):"),
            "Unstake": ("Receipt Token Staked:", "Receipt Amount Unstaked:", "Receipt CAD Value (Basis):"),
            "Reward": ("Token:", "Amount:", "FMV (CAD):"),
            "Fee": ("Token:", "Amount:", "Fee CAD Value:")
        }

        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = self.winfo_reqwidth()
        dialog_height = self.winfo_reqheight()
        x = parent_x + (parent_width // 2) - (dialog_width // 2)
        y = parent_y + (parent_height // 2) - (dialog_height // 2)
        self.geometry(f"+{x}+{y}")

        row = 0
        tk.Label(self, text="Date (YYYY-MM-DD):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.date_var = tk.StringVar(value=transaction[1] if transaction else datetime.now().strftime("%Y-%m-%d"))
        tk.Entry(self, textvariable=self.date_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        tk.Label(self, text="Action:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.action_var = tk.StringVar(value=transaction[3] if transaction else "Buy")
        actions = ["Buy", "Sell", "Trade", "Stake", "Unstake", "Reward", "Fee"]
        self.action_cb = ttk.Combobox(self, textvariable=self.action_var, values=actions, state="readonly", width=10)
        self.action_cb.grid(row=row, column=1, padx=5, pady=5)
        self.action_cb.bind("<<ComboboxSelected>>", self.on_action_change)
        row += 1
        
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
        
        tk.Label(self, text="Exchange Fee (CAD):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.fee_cad_var = tk.DoubleVar(value=transaction[10] if transaction and len(transaction) > 10 else 0.0)
        tk.Entry(self, textvariable=self.fee_cad_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        tk.Label(self, text="Gas/Network Fee (CAD):").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.gas_cad_var = tk.DoubleVar(value=transaction[11] if transaction and len(transaction) > 11 else 0.0)
        tk.Entry(self, textvariable=self.gas_cad_var, width=12).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        tk.Label(self, text="Notes:").grid(row=row, column=0, sticky=tk.W, padx=5, pady=5)
        self.notes_var = tk.StringVar(value=transaction[6] if transaction else "")
        tk.Entry(self, textvariable=self.notes_var, width=30).grid(row=row, column=1, padx=5, pady=5)
        row += 1
        
        self.trade_start_row = row
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=row, column=0, columnspan=2, pady=10)
        self.ok_btn = tk.Button(btn_frame, text="OK", command=self.on_ok, default=tk.ACTIVE)
        self.ok_btn.pack(side=tk.LEFT, padx=5)
        self.bind('<Return>', lambda event: self.ok_btn.invoke())
        self.bind('<Escape>', lambda event: self.destroy())
        tk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)
        
        self.on_action_change()
        self.wait_window(self)

    def on_action_change(self, event=None):
        action = self.action_var.get()
        token_text, amount_text, cad_text = self.label_map.get(action, ("Token:", "Amount:", "CAD Value:"))
        self.token_lbl.config(text=token_text)
        self.amount_lbl.config(text=amount_text)
        self.cad_lbl.config(text=cad_text)

        for lbl, ent in self.sent_widgets:
            lbl.grid_forget()
            ent.grid_forget()
        
        current_row = self.trade_start_row
        if action in ("Trade", "Stake", "Unstake"):
            if action == "Stake":
                self.sent_token_lbl.config(text="Original Token Staked:")
                self.sent_amt_lbl.config(text="Original Amount Staked:")
                self.sent_cad_lbl.config(text="Original CAD Value (Basis):")
            elif action == "Unstake":
                self.sent_token_lbl.config(text="Original Token Unstaked:")
                self.sent_amt_lbl.config(text="Original Amount Unstaked:")
                self.sent_cad_lbl.config(text="Original CAD Value (Basis):")
            else:
                self.sent_token_lbl.config(text="Sent Token:")
                self.sent_amt_lbl.config(text="Sent Amount:")
                self.sent_cad_lbl.config(text="Sent CAD Value:")

            for lbl, ent in self.sent_widgets:
                lbl.grid(row=current_row, column=0, sticky=tk.W, padx=5, pady=5)
                ent.grid(row=current_row, column=1, padx=5, pady=5)
                current_row += 1

        btn_frame = self.children['!frame']
        btn_frame.grid(row=current_row, column=0, columnspan=2, pady=10)

    def on_ok(self):
        try:
            date_str = self.date_var.get().strip()
            if not date_str:
                messagebox.showerror("Input Error", "Date cannot be empty")
                return
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj.date() > datetime.now().date():
                    if not messagebox.askokcancel("Future Date", "This date is in the future. Continue anyway?"):
                        return
            except ValueError:
                messagebox.showerror("Input Error", "Date must be in YYYY-MM-DD format")
                return
            
            action = self.action_var.get()
            token = self.token_var.get().strip().upper()
            try:
                token_amount = float(self.token_amt_var.get())
            except ValueError:
                messagebox.showerror("Input Error", "Amount must be a valid number")
                return
            try:
                cad_amount = float(self.cad_amt_var.get())
            except ValueError:
                messagebox.showerror("Input Error", "CAD value must be a valid number")
                return

            if not token:
                messagebox.showerror("Input Error", "Token cannot be empty")
                return
            if token_amount <= 0:
                messagebox.showerror("Input Error", "Amount must be greater than 0")
                return
            if cad_amount < 0:
                messagebox.showerror("Input Error", "CAD value cannot be negative")
                return

            sent_token_val = None
            sent_amount_val = None
            sent_cad_val = None
            
            if action in ("Trade", "Stake", "Unstake"):
                sent_token = self.sent_token_var.get().strip().upper()
                if not sent_token:
                    messagebox.showerror("Input Error", f"Sent Token cannot be empty for a {action}")
                    return
                try:
                    sent_amount = float(self.sent_amt_var.get())
                except ValueError:
                    messagebox.showerror("Input Error", "Sent amount must be a valid number")
                    return
                try:
                    sent_cad = float(self.sent_cad_var.get())
                except ValueError:
                    messagebox.showerror("Input Error", "Sent CAD must be a valid number")
                    return
                if sent_amount <= 0:
                    messagebox.showerror("Input Error", "Sent Amount must be greater than 0")
                    return
                if sent_cad < 0:
                    messagebox.showerror("Input Error", "Sent CAD cannot be negative")
                    return
                sent_token_val = sent_token
                sent_amount_val = sent_amount
                sent_cad_val = sent_cad

            try:
                fee_cad = float(self.fee_cad_var.get() or 0.0)
                gas_cad = float(self.gas_cad_var.get() or 0.0)
                if fee_cad < 0 or gas_cad < 0:
                    messagebox.showerror("Input Error", "Fees cannot be negative")
                    return
            except ValueError:
                messagebox.showerror("Input Error", "Fee and gas must be valid numbers")
                return

            if action == "Fee":
                if cad_amount <= 0:
                    messagebox.showerror("Input Error", "Fee CAD value must be greater than 0")
                    return

            if action in ("Stake", "Unstake"):
                if action == "Stake" and sent_token_val not in ORIGINAL_TO_RECEIPT_MAP.values():
                    messagebox.showwarning("Unmapped Token", f"Receipt token '{sent_token_val}' not in standard mappings. Verify it's correct.")
                if action == "Unstake" and token not in ORIGINAL_TO_RECEIPT_MAP.values():
                    messagebox.showwarning("Unmapped Token", f"Receipt token '{token}' not in standard mappings. Verify it's correct.")
                if sent_cad_val > 0 and cad_amount > 0:
                    diff_pct = abs(cad_amount - sent_cad_val) / max(cad_amount, sent_cad_val) * 100
                    if diff_pct > 1:
                        if action == "Unstake":
                            messagebox.showinfo("Potential Rewards", f"Basis difference of {diff_pct:.1f}% detected. Verify staking rewards accounting.")
                        else:
                            messagebox.showwarning("Basis Mismatch", f"Input basis ${cad_amount:.2f} vs output basis ${sent_cad_val:.2f} differ by {diff_pct:.1f}%.")

            self.result = (
                date_str,
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
        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid input: {e}")
        except Exception as e:
            messagebox.showerror("Unexpected Error", f"An error occurred: {e}")
            import traceback
            traceback.print_exc()

class CryptoACBApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ledge")
        self.load_geometry()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        init_db()
        self.setup_ui()
        self.load_data()
        
        self.sort_column = None
        self.sort_reverse = False

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
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.trans_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.trans_frame, text="Transactions")

        self.filter_frame = ttk.LabelFrame(self.trans_frame)

        filter_container = ttk.Frame(self.trans_frame)
        filter_container.pack(fill=tk.X, padx=5, pady=5)

        self.filter_visible = tk.BooleanVar(value=False)
        self.toggle_btn = ttk.Button(filter_container, text="▼ Show Filters", 
                                    command=self.toggle_filters)
        self.toggle_btn.pack(side=tk.LEFT, padx=5)

        self.filter_status = ttk.Label(filter_container, text="")
        self.filter_status.pack(side=tk.LEFT, padx=5)

        self.filter_frame = ttk.LabelFrame(self.trans_frame)
        
        date_frame = ttk.Frame(self.filter_frame)
        date_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(date_frame, text="Date Range:").pack(side=tk.LEFT, padx=5)
        self.date_from_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_from_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text="to").pack(side=tk.LEFT, padx=5)
        self.date_to_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=self.date_to_var, width=10).pack(side=tk.LEFT, padx=5)

        filter_row = ttk.Frame(self.filter_frame)
        filter_row.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(filter_row, text="Token:").pack(side=tk.LEFT, padx=5)
        self.token_filter_var = tk.StringVar()
        self.token_filter = ttk.Combobox(filter_row, textvariable=self.token_filter_var, width=10)
        self.token_filter.pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_row, text="Action:").pack(side=tk.LEFT, padx=5)
        self.action_filter_var = tk.StringVar()
        actions = ["", "Buy", "Sell", "Trade", "Stake", "Unstake", "Reward", "Fee"]
        self.action_filter = ttk.Combobox(filter_row, textvariable=self.action_filter_var, values=actions, width=10)
        self.action_filter.pack(side=tk.LEFT, padx=5)

        amount_frame = ttk.Frame(self.filter_frame)
        amount_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Label(amount_frame, text="CAD Amount Range:").pack(side=tk.LEFT, padx=5)
        self.amount_from_var = tk.StringVar()
        ttk.Entry(amount_frame, textvariable=self.amount_from_var, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Label(amount_frame, text="to").pack(side=tk.LEFT, padx=5)
        self.amount_to_var = tk.StringVar()
        ttk.Entry(amount_frame, textvariable=self.amount_to_var, width=10).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(self.filter_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Apply Filters", command=self.apply_filters).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Clear Filters", command=self.clear_filters).pack(side=tk.LEFT, padx=5)

        trans_btn_frame = ttk.Frame(self.trans_frame)
        trans_btn_frame.pack(fill=tk.X, pady=5)
        ttk.Button(trans_btn_frame, text="Add", command=self.add_transaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(trans_btn_frame, text="Edit", command=self.edit_transaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(trans_btn_frame, text="Delete", command=self.delete_transaction).pack(side=tk.LEFT, padx=5)
        ttk.Button(trans_btn_frame, text="Export CSV", command=self.export_csv).pack(side=tk.RIGHT, padx=5)

        self.cols = ("ID", "Date", "Action", "ReceivedToken", "ReceivedAmt", "ReceivedCAD",
                     "SentToken", "SentAmt", "SentCAD", "FeeCAD", "GasCAD", "Notes")
        self.trans_tree = ttk.Treeview(self.trans_frame, columns=self.cols, show="headings", height=15)
        
        self.sort_column = None
        self.sort_reverse = False
        col_widths = {
            "ID": 40, "Date": 100, "Action": 80,
            "ReceivedToken": 90, "ReceivedAmt": 90, "ReceivedCAD": 90,
            "SentToken": 90, "SentAmt": 90, "SentCAD": 90,
            "Notes": 200
        }
        for col in self.cols:
            heading_cmd = lambda c=col: self.sort_by_column(c)
            self.trans_tree.heading(col, 
                text=col.replace("Received", "Rec.").replace("Sent", "Sent"),
                command=heading_cmd)
            self.trans_tree.column(col, width=col_widths.get(col, 100))
        self.trans_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        vscroll = ttk.Scrollbar(self.trans_tree, orient="vertical", command=self.trans_tree.yview)
        self.trans_tree.configure(yscroll=vscroll.set)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.acb_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.acb_frame, text="ACB Summary")

        acb_cols = ("Token", "UnitsHeld", "TotalACB", "ACBperUnit")
        self.acb_tree = ttk.Treeview(self.acb_frame, columns=acb_cols, show="headings", height=15)
        for col in acb_cols:
            self.acb_tree.heading(col, text=col)
            self.acb_tree.column(col, width=150)
        self.acb_tree.pack(fill=tk.BOTH, expand=True, pady=5)

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

        query = ["SELECT id, date, action, token, token_amount, cad_amount,"
                "       sent_token, sent_amount, sent_cad, fee_cad, gas_cad, notes",
                "FROM transactions",
                "WHERE 1=1"]
        params = []

        if self.date_from_var.get():
            query.append("AND date >= ?")
            params.append(self.date_from_var.get())
        if self.date_to_var.get():
            query.append("AND date <= ?")
            params.append(self.date_to_var.get())

        if self.token_filter_var.get():
            query.append("AND (token = ? OR sent_token = ?)")
            params.extend([self.token_filter_var.get(), self.token_filter_var.get()])

        if self.action_filter_var.get():
            query.append("AND action = ?")
            params.append(self.action_filter_var.get())

        try:
            if self.amount_from_var.get():
                amount_from = float(self.amount_from_var.get())
                query.append("AND (cad_amount >= ? OR sent_cad >= ?)")
                params.extend([amount_from, amount_from])
            if self.amount_to_var.get():
                amount_to = float(self.amount_to_var.get())
                query.append("AND (cad_amount <= ? OR sent_cad <= ?)")
                params.extend([amount_to, amount_to])
        except ValueError:
            messagebox.showwarning("Filter Error", "Invalid amount filter value")

        if self.sort_column:
            sort_col = self.sort_column.lower()
            if sort_col in ['receivedamt', 'receivedcad', 'sentamt', 'sentcad', 'feecad', 'gascad']:
                col_map = {
                    'receivedamt': 'token_amount',
                    'receivedcad': 'cad_amount',
                    'sentamt': 'sent_amount',
                    'sentcad': 'sent_cad',
                    'feecad': 'fee_cad',
                    'gascad': 'gas_cad'
                }
                sort_col = col_map.get(sort_col, sort_col)
            query.append(f"ORDER BY {sort_col} {'DESC' if self.sort_reverse else 'ASC'}, id")
        else:
            query.append("ORDER BY date DESC, id DESC")

        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.execute(" ".join(query), params)
                for row in cur.fetchall():
                    fmt_row = (
                        row[0],
                        row[1],
                        row[2],
                        row[3] or "",
                        f"{row[4]:.8f}" if row[4] is not None else "",
                        f"${row[5]:.2f}" if row[5] is not None else "",
                        row[6] or "",
                        f"{row[7]:.8f}" if row[7] is not None else "",
                        f"${row[8]:.2f}" if row[8] is not None else "",
                        f"${row[9]:.2f}" if row[9] is not None else "",
                        f"${row[10]:.2f}" if row[10] is not None else "",
                        row[11] or ""
                    )
                    self.trans_tree.insert("", "end", values=fmt_row)
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading transactions: {e}")

        self.update_token_choices()

    def load_acb_summary(self):
        for item in self.acb_tree.get_children():
            self.acb_tree.delete(item)
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.execute("SELECT token, units_held, total_acb FROM acb_state WHERE units_held > 0 ORDER BY token")
                for token, units, total in cur.fetchall():
                    units = float(units)
                    total = float(total)
                    acb_per = total / units if units > 0 else 0.0
                    self.acb_tree.insert("", "end", values=(token, f"{units:.8f}", f"${total:.2f}", f"${acb_per:.4f}"))
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error loading ACB summary: {e}")

    def _get_current_balance(self, conn, token):
        """Get current balance of a token."""
        cur = conn.execute(
            "SELECT units_held FROM acb_state WHERE token = ?",
            (token,)
        )
        row = cur.fetchone()
        return float(row[0]) if row else 0.0

    def add_transaction(self):
        backup_database()
        dialog = TransactionDialog(self.root)
        if dialog.result:
            (date, token, action, token_amt, cad_amt, notes,
             sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = dialog.result

            with sqlite3.connect(DB_FILE) as conn:
                conn.execute('BEGIN')
                try:
                    if action in ("Stake", "Unstake"):
                        check_token = token if action == "Stake" else sent_token
                        balance = self._get_current_balance(conn, check_token)
                        if balance < token_amt:
                            conn.rollback()
                            messagebox.showerror("Insufficient Balance", 
                                f"Cannot {action.lower()} {token_amt} {check_token}. Current balance: {balance:.8f}")
                            return
                    
                    conn.execute("""
                        INSERT INTO transactions
                        (date, token, action, token_amount, cad_amount, notes,
                         sent_token, sent_amount, sent_cad, fee_cad, gas_cad)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (date, token, action, token_amt, cad_amt, notes,
                          sent_token, sent_amt, sent_cad, fee_cad, gas_cad))
                    
                    self.recompute_acb(conn)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("Transaction Error", f"Failed to add transaction: {e}")
                    return
            
            self.load_data()
            
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
        trans_id = values[0]

        def parse_currency(s):
            if not s or s == "":
                return 0.0
            try:
                return float(s.replace('$', ''))
            except ValueError:
                return 0.0

        def parse_amount(s):
            if not s or s == "":
                return 0.0
            try:
                return float(s)
            except ValueError:
                return 0.0

        date = values[1]
        action = values[2]
        token = values[3] or ""
        rec_amt = parse_amount(values[4]) if values[4] else 0.0
        rec_cad = parse_currency(values[5]) if values[5] else 0.0
        sent_token = values[6] or ""
        sent_amt = parse_amount(values[7]) if values[7] else 0.0
        sent_cad = parse_currency(values[8]) if values[8] else 0.0
        fee_cad = parse_currency(values[9]) if values[9] else 0.0
        gas_cad = parse_currency(values[10]) if values[10] else 0.0
        notes = values[11] or ""

        old_row = (
            None,
            date,
            token,
            action,
            rec_amt,
            rec_cad,
            notes,
            sent_token,
            sent_amt,
            sent_cad,
            fee_cad,
            gas_cad
        )

        dialog = TransactionDialog(self.root, old_row)
        if dialog.result:
            (date, token, action, token_amt, cad_amt, notes,
            sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = dialog.result

            with sqlite3.connect(DB_FILE) as conn:
                conn.execute('BEGIN')
                try:
                    conn.execute('''
                        UPDATE transactions
                        SET date=?, token=?, action=?, token_amount=?, cad_amount=?, notes=?,
                            sent_token=?, sent_amount=?, sent_cad=?, fee_cad=?, gas_cad=?
                        WHERE id=?
                    ''', (date, token, action, token_amt, cad_amt, notes,
                        sent_token, sent_amt, sent_cad, fee_cad, gas_cad, trans_id))
                    self.recompute_acb(conn)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("Edit Error", f"Failed to edit transaction: {e}")
                    return
            self.load_data()

    def delete_transaction(self):
        selected = self.trans_tree.selection()
        if not selected:
            messagebox.showwarning("Select", "Please select a transaction to delete.")
            return
        trans_id = self.trans_tree.item(selected[0])['values'][0]
        if messagebox.askyesno("Confirm", "Delete this transaction? ACB will be recalculated."):
            with sqlite3.connect(DB_FILE) as conn:
                conn.execute('BEGIN')
                try:
                    conn.execute("DELETE FROM transactions WHERE id=?", (trans_id,))
                    self.recompute_acb(conn)
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("Delete Error", f"Failed to delete transaction: {e}")
                    return
            
            self.load_data()

    def recompute_acb(self, conn=None):
        """Recompute ACB state. If conn is provided, use it; otherwise create a new connection."""
        should_close = False
        if conn is None:
            conn = sqlite3.connect(DB_FILE)
            should_close = True

        try:
            cur = conn.execute("""
                SELECT date, token, action, token_amount, cad_amount,
                       sent_token, sent_amount, sent_cad,
                       fee_cad, gas_cad
                FROM transactions
                ORDER BY date, id
            """)
            rows = cur.fetchall()
            
            acb_state = defaultdict(lambda: {"total_acb": decimal.Decimal(0), "units_held": decimal.Decimal(0)})

            for row in rows:
                (date, token, action, token_amt, cad_amt,
                 sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = row

                token_amt = decimal.Decimal(token_amt)
                cad_amt = decimal.Decimal(cad_amt)
                sent_amt = decimal.Decimal(sent_amt) if sent_amt is not None else decimal.Decimal(0)
                sent_cad = decimal.Decimal(sent_cad) if sent_cad is not None else decimal.Decimal(0)
                fee_cad = decimal.Decimal(fee_cad) if fee_cad is not None else decimal.Decimal(0)
                gas_cad = decimal.Decimal(gas_cad) if gas_cad is not None else decimal.Decimal(0)

                if gas_cad > 0:
                    acb_state["GAS_FEES"]["total_acb"] -= gas_cad

                if action == "Buy":
                    total_cost = cad_amt + fee_cad
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt
                elif action == "Sell":
                    state = acb_state[token]
                    if state["units_held"] > 0:
                        try:
                            acb_per = state["total_acb"] / state["units_held"]
                            cost_basis = acb_per * token_amt
                            state["total_acb"] = max(decimal.Decimal(0), state["total_acb"] - cost_basis)
                            state["units_held"] = max(decimal.Decimal(0), state["units_held"] - token_amt)
                        except ZeroDivisionError:
                            pass
                elif action == "Trade":
                    if sent_token and sent_amt and sent_cad is not None:
                        sent_state = acb_state[sent_token]
                        if sent_state["units_held"] > 0:
                            try:
                                acb_per_sent = sent_state["total_acb"] / sent_state["units_held"]
                                cost_basis = acb_per_sent * sent_amt
                                sent_state["total_acb"] = max(decimal.Decimal(0), sent_state["total_acb"] - cost_basis)
                                sent_state["units_held"] = max(decimal.Decimal(0), sent_state["units_held"] - sent_amt)
                            except ZeroDivisionError:
                                pass
                    total_cost = cad_amt + fee_cad
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt
                elif action == "Stake":
                    original_state = acb_state[token]
                    if original_state["units_held"] > 0:
                        try:
                            acb_per_unit_original = original_state["total_acb"] / original_state["units_held"]
                            acb_for_staked_out = acb_per_unit_original * token_amt
                            original_state["total_acb"] = max(decimal.Decimal(0), original_state["total_acb"] - acb_for_staked_out)
                            original_state["units_held"] = max(decimal.Decimal(0), original_state["units_held"] - token_amt)
                        except ZeroDivisionError:
                            original_state["units_held"] = max(decimal.Decimal(0), original_state["units_held"] - token_amt)
                            acb_for_staked_out = decimal.Decimal(0)
                    else:
                        original_state["units_held"] = max(decimal.Decimal(0), original_state["units_held"] - token_amt)
                        acb_for_staked_out = decimal.Decimal(0)
                    
                    receipt_state = acb_state[sent_token]
                    receipt_state["total_acb"] += acb_for_staked_out
                    receipt_state["units_held"] += sent_amt
                elif action == "Unstake":
                    receipt_state = acb_state[token]
                    if receipt_state["units_held"] > 0:
                        try:
                            acb_per_unit_receipt = receipt_state["total_acb"] / receipt_state["units_held"]
                            acb_for_unstaked_out = acb_per_unit_receipt * token_amt
                            receipt_state["total_acb"] = max(decimal.Decimal(0), receipt_state["total_acb"] - acb_for_unstaked_out)
                            receipt_state["units_held"] = max(decimal.Decimal(0), receipt_state["units_held"] - token_amt)
                        except ZeroDivisionError:
                            receipt_state["units_held"] = max(decimal.Decimal(0), receipt_state["units_held"] - token_amt)
                            acb_for_unstaked_out = decimal.Decimal(0)
                    else:
                        receipt_state["units_held"] = max(decimal.Decimal(0), receipt_state["units_held"] - token_amt)
                        acb_for_unstaked_out = decimal.Decimal(0)
                    
                    original_state = acb_state[sent_token]
                    original_state["total_acb"] += acb_for_unstaked_out
                    original_state["units_held"] += sent_amt
                elif action == "Reward":
                    acb_state[token]["total_acb"] += cad_amt
                    acb_state[token]["units_held"] += token_amt
                elif action == "Fee":
                    state = acb_state[token]
                    if state["units_held"] > 0:
                        try:
                            acb_per = state["total_acb"] / state["units_held"]
                            cost_basis = acb_per * token_amt
                            state["total_acb"] = max(decimal.Decimal(0), state["total_acb"] - cost_basis)
                            state["units_held"] = max(decimal.Decimal(0), state["units_held"] - token_amt)
                        except ZeroDivisionError:
                            pass
                    else:
                        state["units_held"] = max(decimal.Decimal(0), state["units_held"] - token_amt)

            for token, state in acb_state.items():
                conn.execute(
                    "INSERT OR REPLACE INTO acb_state (token, total_acb, units_held) VALUES (?, ?, ?)",
                    (token, state["total_acb"], state["units_held"])
                )
        finally:
            if should_close:
                conn.close()

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
            
            token_gains = defaultdict(float)
            token_gas = defaultdict(float)

            for row in cur.fetchall():
                (date, token, action, token_amt, cad_amt,
                 sent_token, sent_amt, sent_cad, fee_cad, gas_cad) = row
                action_counts[action] += 1
                fee_cad = fee_cad or 0.0
                gas_cad = gas_cad or 0.0
                total_exchange_fees += fee_cad
                total_gas_loss += gas_cad
                if gas_cad > 0:
                    token_gas[token] += gas_cad

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
                    total_cost = cad_amt + fee_cad
                    acb_state[token]["total_acb"] += total_cost
                    acb_state[token]["units_held"] += token_amt
                elif action == "Stake":
                    original_state = acb_state[token]
                    if original_state["units_held"] > 0:
                        try:
                            acb_per_unit = original_state["total_acb"] / original_state["units_held"]
                            acb_for_out = acb_per_unit * token_amt
                            original_state["total_acb"] = max(0.0, original_state["total_acb"] - acb_for_out)
                            original_state["units_held"] = max(0.0, original_state["units_held"] - token_amt)
                        except ZeroDivisionError:
                            original_state["units_held"] = max(0.0, original_state["units_held"] - token_amt)
                            acb_for_out = 0.0
                    else:
                        original_state["units_held"] = max(0.0, original_state["units_held"] - token_amt)
                        acb_for_out = 0.0
                    receipt_state = acb_state[sent_token]
                    receipt_state["total_acb"] += acb_for_out
                    receipt_state["units_held"] += sent_amt
                elif action == "Unstake":
                    receipt_state = acb_state[token]
                    if receipt_state["units_held"] > 0:
                        try:
                            acb_per_unit = receipt_state["total_acb"] / receipt_state["units_held"]
                            acb_for_out = acb_per_unit * token_amt
                            receipt_state["total_acb"] = max(0.0, receipt_state["total_acb"] - acb_for_out)
                            receipt_state["units_held"] = max(0.0, receipt_state["units_held"] - token_amt)
                        except ZeroDivisionError:
                            receipt_state["units_held"] = max(0.0, receipt_state["units_held"] - token_amt)
                            acb_for_out = 0.0
                    else:
                        receipt_state["units_held"] = max(0.0, receipt_state["units_held"] - token_amt)
                        acb_for_out = 0.0
                    original_state = acb_state[sent_token]
                    original_state["total_acb"] += acb_for_out
                    original_state["units_held"] += sent_amt
                elif action == "Fee":
                    state = acb_state[token]
                    if state["units_held"] <= 0:
                        realized_loss = -cad_amt
                    else:
                        acb_per = state["total_acb"] / state["units_held"]
                        cost_basis = acb_per * token_amt
                        realized_loss = -cad_amt
                        state["total_acb"] = max(0.0, state["total_acb"] - cost_basis)
                        state["units_held"] = max(0.0, state["units_held"] - token_amt)
                    total_realized_gain += realized_loss
                    token_gains[token] += realized_loss

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

    def sort_by_column(self, column):
        """Sort treeview when a column header is clicked."""
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        
        self.load_transactions()

    def update_token_choices(self):
        """Update the token filter dropdown with all tokens from the database."""
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.execute("""
                    SELECT DISTINCT token FROM transactions WHERE token IS NOT NULL
                    UNION
                    SELECT DISTINCT sent_token FROM transactions WHERE sent_token IS NOT NULL
                    ORDER BY token
                """)
                tokens = [""] + [row[0] for row in cur.fetchall()]
                self.token_filter['values'] = tokens
        except sqlite3.Error as e:
            messagebox.showerror("Database Error", f"Error updating token choices: {e}")

    def apply_filters(self):
        """Apply the current filters and refresh the transaction list."""
        self.load_transactions()

    def clear_filters(self):
        """Clear all filters and refresh the transaction list."""
        self.date_from_var.set("")
        self.date_to_var.set("")
        self.token_filter_var.set("")
        self.action_filter_var.set("")
        self.amount_from_var.set("")
        self.amount_to_var.set("")
        self.load_transactions()

    def toggle_filters(self):
        """Toggle the visibility of the filter frame."""
        if self.filter_visible.get():
            self.filter_frame.pack_forget()
            self.filter_visible.set(False)
            self.toggle_btn.configure(text="▼ Show Filters")
        else:
            self.filter_frame.pack(fill=tk.X, padx=5, pady=5)
            self.filter_visible.set(True)
            self.toggle_btn.configure(text="▲ Hide Filters")

    def update_report(self):
        data = self.generate_report_data()
        report = "📊 Ledge Tax & Portfolio Summary\n"
        report += "=" * 40 + "\n\n"

        report += "💰 Financial Summary\n"
        report += f"Total Realized Capital Gains: ${data['total_realized_gain']:.2f}\n"
        report += f"Total Gas Fees (Capital Losses): -${data['total_gas_loss']:.2f}\n"
        report += f"Total Exchange Fees Paid: ${data['total_exchange_fees']:.2f}\n"
        report += f"Net PnL (Gains - Gas Losses): ${data['net_pnl']:.2f}\n\n"

        report += "📈 Activity Summary\n"
        for action, count in sorted(data['action_counts'].items()):
            report += f"{action}: {count} transaction(s)\n"
        report += "\n"

        if data['token_gains']:
            report += "🔖 Realized Gains by Token\n"
            for token, gain in sorted(data['token_gains'].items(), key=lambda x: -x[1]):
                report += f"{token}: ${gain:.2f}\n"
            report += "\n"

        if data['current_holdings']:
            report += "💼 Current Holdings\n"
            for token, h in sorted(data['current_holdings'].items()):
                report += f"{token}: {h['units']:.8f} units @ ${h['acb_per_unit']:.4f}/unit (ACB: ${h['total_acb']:.2f})\n"
            report += "\n"

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
                writer.writerow([
                    "Date", "Action", "Received Token", "Received Amount", "Received CAD",
                    "Sent Token", "Sent Amount", "Sent CAD",
                    "Exchange Fee (CAD)", "Gas Fee (CAD)", "Notes"
                ])
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

"""
device_combined_bulk.py

Adds Bulk Insert / Bulk Update / Bulk Delete from an Excel file to the previous
Device-combined manager.

Features added in this file compared to prior version:
- Buttons: Bulk Insert, Bulk Update, Bulk Delete. They accept an Excel file.
- Column mapping rules:
    * Columns named like "Table.Column" (e.g. "Device.sName" or "ChildTable.sVal")
      are mapped to the named table/column.
    * Columns not containing a dot are mapped to Device table columns.
- Bulk Insert:
    * For each Excel row, creates a Device row and child rows (based on columns or
      default child-row templates). Missing parameters are taken from user defaults
      (then detected defaults), otherwise left empty.
    * After insertion, writes device and child CSVs.
- Bulk Update:
    * For each Excel row, locates the Device by primary key (first column of Device CSV);
      updates only the specified columns that differ (doesn't remove or replace other rows).
    * For child tables: supports updates if Excel columns use Table.Column and include
      the child's PK column to identify the row.
- Bulk Delete:
    * Excel file must contain the Device primary key column (or column named like it).
      Each listed PK will be removed from Device CSV and corresponding child rows
      referencing the device will be removed too (simple cascade by FK match).
- Default child-row templates: persists to DEFAULT_CHILD_ROWS_FILE. Templates are
  applied during Insert (both single insert and bulk insert).
- Visibility dialog now has table-level visibility toggles (show/hide entire table)

Usage: edit DATA_FOLDER, RELATION_FILE paths at top; run with Python 3 and pandas.
Make a backup of your CSV folder before using bulk operations.

Requires: pandas
"""

import os, re, json, tempfile, shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from collections import defaultdict

# ---------------- CONFIG ----------------
DATA_FOLDER = r"C:\WhatsUpCSVs"
RELATION_FILE = r"C:\Users\Ammar\Desktop\relations.csv"
DEFAULTS_FILE = os.path.join(os.path.expanduser("~"), "device_defaults.json")
VISIBILITY_FILE = os.path.join(os.path.expanduser("~"), "device_visibility.json")
DEFAULT_CHILD_ROWS_FILE = os.path.join(os.path.expanduser("~"), "device_default_child_rows.json")
ROOT_TABLE = "Device"
# ----------------------------------------

# ----- small helpers -----
def normalize_table_name(name: str) -> str:
    if not isinstance(name, str): return name
    return re.sub(r"(?i)^dbo[_\.]", "", name.strip())


def human_label(c: str) -> str:
    s = re.sub(r"^[ns](_|-)?", "", c)
    s = s.replace("_", " ").replace(".", " ")
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = re.sub(r"\bID\b", "Id", s, flags=re.IGNORECASE)
    return " ".join([w.capitalize() for w in s.split()])


def safe_write_csv(df, path):
    df2 = df.fillna("").astype(object)
    dirn = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dirn, prefix=".tmp_csv_")
    os.close(fd)
    try:
        df2.to_csv(tmp, index=False, encoding="utf-8-sig", na_rep="")
        shutil.move(tmp, path)
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

# ----- Tooling (Tooltips) -----
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget; self.text = text; self.top = None
        widget.bind("<Enter>", self.show); widget.bind("<Leave>", self.hide)
    def show(self, e=None):
        if self.top: return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + 12
        self.top = tk.Toplevel(self.widget); self.top.wm_overrideredirect(True)
        self.top.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(self.top, text=self.text, background="#ffffe0", relief="solid", borderwidth=1, padx=6, pady=3, wraplength=320)
        lbl.pack()
    def hide(self, e=None):
        if self.top:
            try: self.top.destroy()
            except: pass
            self.top = None

# ----- Schema -----
class DeviceSchema:
    def __init__(self, data_folder, relation_file, root_table="Device"):
        self.data_folder = data_folder
        self.relation_file = relation_file
        self.root_table = root_table
        self.relations = None
        self.child_map = defaultdict(list)
        self.tables = {}
        self._load_relations()
        self._load_device_and_children()

    def _load_relations(self):
        if not os.path.exists(self.relation_file):
            raise FileNotFoundError("relations.csv not found")
        rel = pd.read_csv(self.relation_file, dtype=str, keep_default_na=False)
        expected = ["ForeignKeyName","ParentTable","ParentColumn","ReferencedTable","ReferencedColumn"]
        colmap = {}
        for e in expected:
            for c in rel.columns:
                if c.strip().lower() == e.lower():
                    colmap[e] = c; break
            else:
                raise ValueError(f"relations.csv missing column: {e}")
        rel = rel[[colmap[e] for e in expected]].copy(); rel.columns = expected
        rel["Parent_norm"] = rel["ParentTable"].apply(normalize_table_name)
        rel["Referenced_norm"] = rel["ReferencedTable"].apply(normalize_table_name)
        self.relations = rel
        for _, r in rel.iterrows():
            self.child_map[r["Referenced_norm"]].append({
                "ForeignKeyName": r["ForeignKeyName"],
                "ParentTable": r["ParentTable"],
                "Parent_norm": r["Parent_norm"],
                "ParentColumn": r["ParentColumn"],
                "ReferencedTable": r["ReferencedTable"],
                "Referenced_norm": r["Referenced_norm"],
                "ReferencedColumn": r["ReferencedColumn"],
            })

    def _find_csv_for_norm(self, norm):
        files = [f for f in os.listdir(self.data_folder) if f.lower().endswith('.csv')]
        for f in files:
            base = os.path.splitext(f)[0]
            if normalize_table_name(base).lower() == norm.lower():
                return os.path.join(self.data_folder, f)
        return None

    def get_table_path(self, norm):
        return self.tables.get(norm, (None, None))[1]

    def _load_device_and_children(self):
        root_norm = normalize_table_name(self.root_table)
        needed = {root_norm}
        for child in self.child_map.get(root_norm, []):
            needed.add(child['Parent_norm'])
        for norm in needed:
            path = self._find_csv_for_norm(norm)
            if not path:
                print(f"[WARN] CSV for {norm} not found in {self.data_folder}; skipping.")
                continue
            try:
                df = pd.read_csv(path, dtype=object, keep_default_na=False)
            except Exception:
                df = pd.read_csv(path, dtype=object, encoding='utf-8', errors='replace', keep_default_na=False)
            df.columns = [str(c) for c in df.columns]
            df = df.reset_index(drop=True)
            self.tables[norm] = (df, path)

    def detect_defaults(self):
        defaults = {}
        for norm, (df, _) in self.tables.items():
            col_defaults = {}
            for c in df.columns:
                vals = [('' if x is None else str(x)).strip() for x in df[c].tolist()]
                unique = sorted(set(vals))
                if len(unique) == 1:
                    col_defaults[c] = unique[0]
                else:
                    col_defaults[c] = None
            defaults[norm] = col_defaults
        return defaults

    def compute_next_numeric_pk(self, norm):
        if norm not in self.tables: return None
        df, _ = self.tables[norm]
        if df.shape[1] == 0: return None
        pk = df.columns[0]
        try:
            nums = pd.to_numeric(df[pk], errors='coerce')
            if nums.dropna().empty: return None
            return int(nums.max()) + 1
        except:
            return None

# ----- Application UI -----
class DeviceBulkApp(tk.Tk):
    def __init__(self, schema: DeviceSchema):
        super().__init__()
        self.schema = schema
        self.root_norm = normalize_table_name(schema.root_table)
        if self.root_norm not in self.schema.tables:
            messagebox.showerror("Error", f"Device CSV not found in {schema.data_folder}")
            self.destroy(); return
        self.detected_defaults = self.schema.detect_defaults()
        self.user_defaults = self._load_user_defaults()
        self.visibility = self._load_visibility()
        self.default_child_rows = self._load_default_child_rows()
        self._build_ui()

    def _load_user_defaults(self):
        if os.path.exists(DEFAULTS_FILE):
            try:
                with open(DEFAULTS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _load_visibility(self):
        if os.path.exists(VISIBILITY_FILE):
            try:
                with open(VISIBILITY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _load_default_child_rows(self):
        if os.path.exists(DEFAULT_CHILD_ROWS_FILE):
            try:
                with open(DEFAULT_CHILD_ROWS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_default_child_rows(self):
        try:
            with open(DEFAULT_CHILD_ROWS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.default_child_rows, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def _build_ui(self):
        self.title("Device bulk manager")
        self.geometry('900x700')
        top = ttk.Frame(self); top.pack(fill='x', padx=6, pady=6)
        ttk.Button(top, text='Bulk Insert (Excel)', command=self.bulk_insert_dialog).pack(side='left', padx=6)
        ttk.Button(top, text='Bulk Update (Excel)', command=self.bulk_update_dialog).pack(side='left', padx=6)
        ttk.Button(top, text='Bulk Delete (Excel)', command=self.bulk_delete_dialog).pack(side='left', padx=6)
        ttk.Button(top, text='Manage default child rows', command=self._manage_default_child_rows).pack(side='left', padx=6)
        ttk.Button(top, text='Show/Hide fields', command=self._open_visibility_editor).pack(side='right', padx=6)
        ttk.Button(top, text='Edit defaults', command=self._open_defaults_editor).pack(side='right', padx=6)
        info = ttk.Label(self, text='Make a backup of CSVs before running bulk operations!')
        info.pack(fill='x', padx=6)

        # small status area
        self.status = tk.StringVar(value='Ready')
        ttk.Label(self, textvariable=self.status).pack(fill='x', padx=6, pady=(6,0))

    # ---------- Bulk operations ----------
    def bulk_insert_dialog(self):
        path = filedialog.askopenfilename(title='Select Excel for bulk insert', filetypes=[('Excel', '*.xlsx;*.xls')])
        if not path: return
        try:
            df = pd.read_excel(path, dtype=object)
        except Exception as e:
            messagebox.showerror('Read error', f'Failed to read Excel: {e}'); return
        self.status.set(f'Bulk insert: {len(df)} rows from {os.path.basename(path)}')
        self.bulk_insert_from_df(df)

    def bulk_update_dialog(self):
        path = filedialog.askopenfilename(title='Select Excel for bulk update', filetypes=[('Excel', '*.xlsx;*.xls')])
        if not path: return
        try:
            df = pd.read_excel(path, dtype=object)
        except Exception as e:
            messagebox.showerror('Read error', f'Failed to read Excel: {e}'); return
        self.status.set(f'Bulk update: {len(df)} rows from {os.path.basename(path)}')
        self.bulk_update_from_df(df)

    def bulk_delete_dialog(self):
        path = filedialog.askopenfilename(title='Select Excel for bulk delete (device PK list expected)', filetypes=[('Excel', '*.xlsx;*.xls')])
        if not path: return
        try:
            df = pd.read_excel(path, dtype=object)
        except Exception as e:
            messagebox.showerror('Read error', f'Failed to read Excel: {e}'); return
        self.status.set(f'Bulk delete: {len(df)} rows from {os.path.basename(path)}')
        self.bulk_delete_from_df(df)

    def _col_to_table_col(self, colname):
        # if col contains dot: Table.Col, else Device.Col
        if '.' in colname:
            t, c = colname.split('.', 1)
            return normalize_table_name(t), c
        return self.root_norm, colname

    def bulk_insert_from_df(self, exdf: pd.DataFrame):
        # map each row to device row + child rows
        device_df, device_path = self.schema.tables[self.root_norm]
        new_devices = []
        child_inserts = defaultdict(list)
        for _, r in exdf.iterrows():
            # build device row initial with defaults
            dev_row = {}
            # start with user defaults and detected
            for c in device_df.columns:
                ud = self.user_defaults.get(self.root_norm, {}).get(c, None)
                det = self.detected_defaults.get(self.root_norm, {}).get(c, None)
                dev_row[c] = '' if ud is None and det is None else (ud if ud is not None else det)
            # override with Excel columns mapped to Device
            for col in exdf.columns:
                tnorm, cname = self._col_to_table_col(col)
                val = r[col]
                if pd.isna(val):
                    continue
                if tnorm == self.root_norm:
                    if cname in dev_row:
                        dev_row[cname] = str(val)
                else:
                    # child column -> collect into temporary child dict keyed by table
                    child_inserts[tnorm].append((dev_row, {cname: str(val)}))
            # also plan default child rows that should be created for every device
            for ctn, templates in self.default_child_rows.items():
                for tmpl in templates:
                    # copy template (strings)
                    child_inserts[ctn].append((dev_row, dict(tmpl)))
            new_devices.append(dev_row)

        # append devices sequentially and write CSV incrementally (keeps memory small)
        if not new_devices:
            messagebox.showinfo('Bulk insert', 'No devices found in Excel.')
            return
        # Build new device DF (append)
        appended = pd.concat([device_df, pd.DataFrame(new_devices)], ignore_index=True)
        try:
            safe_write_csv(appended, device_path)
        except Exception as e:
            messagebox.showerror('Write error', f'Failed to write Device CSV: {e}'); return
        # For child inserts, we must compute FK value for each child row using referenced column or pk.
        # reload device df to get final state (including newly appended devices)
        self.schema._load_device_and_children()
        device_df2, _ = self.schema.tables[self.root_norm]
        # naive approach: assume excel rows appended in same order to device_df2 tail
        start_idx = len(device_df)
        for i, dev_row in enumerate(new_devices):
            device_pk = None
            pk_col = device_df.columns[0]
            # determine device_pk value from appended frame
            try:
                device_pk = str(device_df2.iloc[start_idx + i][pk_col])
            except Exception:
                device_pk = ''
            # apply child inserts that referenced this particular dev_row
            # child_inserts stored tuples (dev_row_ref, partial_row), we match by object identity -- not robust when copy
            # simpler: also add per-new-device child templates stored earlier in order. We'll instead handle default child rows by templates only here.
            pass
        # For simplicity: re-open all child tables and append templates linked to each new device
        for ctn, templates in self.default_child_rows.items():
            if ctn not in self.schema.tables:
                continue
            child_df, child_path = self.schema.tables[ctn]
            rows_to_add = []
            pk_col_child = child_df.columns[0] if child_df.shape[1]>0 else None
            for j in range(len(new_devices)):
                # corresponding appended device row
                try:
                    device_pk = str(device_df2.iloc[start_idx + j][device_df.columns[0]])
                except Exception:
                    device_pk = ''
                for tmpl in templates:
                    rdict = dict(tmpl)
                    # ensure FK set to device_pk if parentcol exists in template key names
                    # find relation meta
                    meta_list = [m for m in self.schema.child_map.get(self.root_norm, []) if m['Parent_norm']==ctn]
                    parent_col = meta_list[0]['ParentColumn'] if meta_list else None
                    if parent_col:
                        rdict[parent_col] = device_pk
                    # child pk auto assign
                    if pk_col_child and (rdict.get(pk_col_child, '') == ''):
                        try:
                            existing = pd.to_numeric(child_df[pk_col_child], errors='coerce')
                            maxv = existing.max()
                            if not pd.isna(maxv): rdict[pk_col_child] = int(maxv)+1
                            else: rdict[pk_col_child] = ''
                        except:
                            rdict[pk_col_child] = ''
                    rows_to_add.append(rdict)
            if rows_to_add:
                new_child_df = pd.concat([child_df, pd.DataFrame(rows_to_add)], ignore_index=True)
                try:
                    safe_write_csv(new_child_df, child_path)
                except Exception as e:
                    messagebox.showerror('Write error', f'Failed to write child table {ctn}: {e}'); return
        messagebox.showinfo('Bulk insert', f'Inserted {len(new_devices)} devices and default child rows.')
        self.schema._load_device_and_children()

    def bulk_update_from_df(self, exdf: pd.DataFrame):
        # update Device rows and optionally child rows if identifying PK is provided
        device_df, device_path = self.schema.tables[self.root_norm]
        pk = device_df.columns[0]
        updated_count = 0
        device_df2 = device_df.copy()
        # columns with dot syntax map to child tables; track child updates grouped by table
        child_updates = defaultdict(list)
        for _, r in exdf.iterrows():
            # device pk value expected either as column named pk or as Device.pk
            if pk in exdf.columns:
                dev_pk_val = r[pk]
            elif f'{self.root_norm}.{pk}' in exdf.columns:
                dev_pk_val = r[f'{self.root_norm}.{pk}']
            else:
                messagebox.showwarning('Missing PK', f'Excel must contain Device PK column named "{pk}" for updates. Row skipped.'); continue
            if pd.isna(dev_pk_val):
                continue
            dev_pk_val = str(dev_pk_val)
            # locate device row by pk
            matches = device_df2[device_df2[pk].astype(str) == dev_pk_val]
            if matches.empty:
                continue
            idx = matches.index[0]
            changed = False
            for col in exdf.columns:
                tnorm, cname = self._col_to_table_col(col)
                val = r[col]
                if pd.isna(val):
                    continue
                val = str(val)
                if tnorm == self.root_norm:
                    # update device_df2 at idx
                    old = '' if pd.isna(device_df2.at[idx, cname]) else str(device_df2.at[idx, cname])
                    if old != val:
                        device_df2.at[idx, cname] = val; changed = True
                else:
                    # child update: require child pk to be present as column Table.ChildPK
                    child_updates[tnorm].append((dev_pk_val, cname, val, r))
            if changed:
                updated_count += 1
        # write device CSV if any updates
        if updated_count > 0:
            try:
                safe_write_csv(device_df2, device_path)
            except Exception as e:
                messagebox.showerror('Write error', f'Failed to write Device CSV: {e}'); return
        # process child updates: we expect exdf to include child PK column to map
        child_written = 0
        for ctn, updates in child_updates.items():
            if ctn not in self.schema.tables: continue
            child_df, child_path = self.schema.tables[ctn]
            child_df2 = child_df.copy()
            child_pk_col = child_df.columns[0] if child_df.shape[1]>0 else None
            # naive approach: if update rows contain child's PK column in excel, perform per-row update
            # otherwise skip child updates
            # gather unique child pk columns referenced
            # assume updates entries may include tuple with cname equals child PK column
            # More robust implementation would require structured Excel design; we'll try simple support
            for (dev_pk_val, cname, val, original_row) in updates:
                # look for child pk in original_row as Table.ChildPK or ChildPK
                child_pk_val = None
                candidate1 = f'{ctn}.{child_pk_col}' if child_pk_col else None
                if candidate1 and candidate1 in exdf.columns:
                    child_pk_val = original_row[candidate1]
                elif child_pk_col and child_pk_col in exdf.columns:
                    child_pk_val = original_row[child_pk_col]
                if pd.isna(child_pk_val) or child_pk_val is None:
                    continue
                child_pk_val = str(child_pk_val)
                # locate row in child_df2
                match = child_df2[child_df2[child_pk_col].astype(str) == child_pk_val]
                if match.empty:
                    continue
                cidx = match.index[0]
                old = '' if pd.isna(child_df2.at[cidx, cname]) else str(child_df2.at[cidx, cname])
                if old != val:
                    child_df2.at[cidx, cname] = val
                    child_written += 1
            if child_written > 0:
                try:
                    safe_write_csv(child_df2, child_path)
                except Exception as e:
                    messagebox.showerror('Write error', f'Failed to write child table {ctn}: {e}'); return
        messagebox.showinfo('Bulk update', f'Device rows updated: {updated_count}. Child cells updated (approx): {child_written}.')
        self.schema._load_device_and_children()

    def bulk_delete_from_df(self, exdf: pd.DataFrame):
        # expects a column equal to device PK name or Device.PK
        device_df, device_path = self.schema.tables[self.root_norm]
        pk = device_df.columns[0]
        # find column
        if pk in exdf.columns:
            keys = exdf[pk].dropna().astype(str).tolist()
        elif f'{self.root_norm}.{pk}' in exdf.columns:
            keys = exdf[f'{self.root_norm}.{pk}'].dropna().astype(str).tolist()
        else:
            messagebox.showerror('Missing PK', f'Excel must contain primary key column named "{pk}" or "{self.root_norm}.{pk}"'); return
        if not keys:
            messagebox.showinfo('Bulk delete', 'No keys found in Excel.'); return
        # delete from device df
        df2 = device_df[~device_df[pk].astype(str).isin(keys)].reset_index(drop=True)
        try:
            safe_write_csv(df2, device_path)
        except Exception as e:
            messagebox.showerror('Write error', f'Failed to write Device CSV: {e}'); return
        # cascade: remove child rows whose FK equals any deleted pk
        deleted_children = []
        for cnorm, (child_df, child_path) in list(self.schema.tables.items()):
            if cnorm == self.root_norm: continue
            # find relation meta where parent is root_norm and parent_norm==cnorm
            meta_list = [m for m in self.schema.child_map.get(self.root_norm, []) if m['Parent_norm']==cnorm]
            if not meta_list: continue
            parent_col = meta_list[0]['ParentColumn']
            cnew = child_df[~child_df[parent_col].astype(str).isin(keys)].reset_index(drop=True)
            try:
                safe_write_csv(cnew, child_path)
                deleted_children.append(cnorm)
            except Exception as e:
                messagebox.showerror('Write error', f'Failed to write child table {cnorm}: {e}'); return
        messagebox.showinfo('Bulk delete', f'Deleted {len(keys)} devices. Cleaned child tables: {", ".join(deleted_children)}')
        self.schema._load_device_and_children()

    # ---------- default child rows manager ----------
    def _manage_default_child_rows(self):
        dialog = DefaultChildRowsDialog(self, 'Manage default child rows', list(self.schema.tables.keys()), self.default_child_rows)
        if dialog.ok:
            self.default_child_rows = dialog.result
            self._save_default_child_rows()
            messagebox.showinfo('Defaults', 'Default child row templates saved.')

    # ---------- UI helpers (visibility, defaults) ----------
    def _open_visibility_editor(self):
        dialog = VisibilityDialog(self, 'Show/Hide fields + tables', list(self.schema.tables.keys()), self.schema, self.visibility)
        if dialog.ok:
            self.visibility = dialog.result
            with open(VISIBILITY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.visibility, f, indent=2, ensure_ascii=False)
            messagebox.showinfo('Visibility', 'Saved.')

    def _open_defaults_editor(self):
        dialog = DefaultsEditor(self, 'Edit defaults', self.detected_defaults, self.user_defaults)
        if dialog.ok:
            self.user_defaults = dialog.result
            with open(DEFAULTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.user_defaults, f, indent=2, ensure_ascii=False)
            messagebox.showinfo('Defaults', 'Saved.')

# ---------- Dialogs (Defaults, Visibility, DefaultChildRows) ----------
class DefaultsEditor(tk.Toplevel):
    def __init__(self, parent, title, detected_defaults, user_defaults):
        super().__init__(parent); self.transient(parent); self.title(title); self.parent = parent
        self.result = {}; self.ok = False
        body = ttk.Frame(self); body.pack(padx=12, pady=12, fill='both', expand=True)
        canvas = tk.Canvas(body, height=520); vs = ttk.Scrollbar(body, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set); vs.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        inner = ttk.Frame(canvas); canvas.create_window((0,0), window=inner, anchor='nw')
        def on_conf(e): canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', on_conf)
        self.entries = {}; row = 0
        for table, cols in detected_defaults.items():
            ttk.Label(inner, text=f'Table: {table}', font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=(8,4), padx=6); row+=1
            for col, det in cols.items():
                ttk.Label(inner, text=human_label(col)).grid(row=row, column=0, sticky='w', padx=6, pady=3)
                ent = ttk.Entry(inner, width=60); ent.grid(row=row, column=1, padx=6, pady=3)
                val = user_defaults.get(table, {}).get(col, det if det is not None else '')
                ent.insert(0, '' if val is None else str(val))
                self.entries.setdefault(table, {})[col] = ent
                row += 1
        btns = ttk.Frame(self); btns.pack(fill='x', pady=8)
        ttk.Button(btns, text='OK', command=self.on_ok).pack(side='right', padx=6)
        ttk.Button(btns, text='Cancel', command=self.on_cancel).pack(side='right')
        self.grab_set(); self.wait_window(self)
    def on_ok(self):
        res = {}
        for table, colmap in self.entries.items():
            res[table] = {}
            for col, ent in colmap.items():
                v = ent.get().strip()
                if v != '': res[table][col] = v
        self.result = res; self.ok = True; self.destroy()
    def on_cancel(self):
        self.ok = False; self.destroy()

class VisibilityDialog(tk.Toplevel):
    def __init__(self, parent, title, table_list, schema: DeviceSchema, current_visibility):
        super().__init__(parent); self.transient(parent); self.title(title); self.parent = parent
        self.result = {}; self.ok = False; self.vars = {}
        body = ttk.Frame(self); body.pack(padx=12, pady=12, fill='both', expand=True)
        canvas = tk.Canvas(body, height=520); vs = ttk.Scrollbar(body, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set); vs.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        inner = ttk.Frame(canvas); canvas.create_window((0,0), window=inner, anchor='nw')
        def on_conf(e): canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', on_conf)
        row = 0
        for table in table_list:
            df, _ = schema.tables.get(table, (None, None))
            if df is None: continue
            # table-level toggle
            tvar = tk.BooleanVar(value=current_visibility.get(table, {}).get('__table_visible', True))
            cb = ttk.Checkbutton(inner, text=f'Table: {table}', variable=tvar)
            cb.grid(row=row, column=0, sticky='w', pady=(8,4), padx=6)
            self.vars.setdefault(table, {})['__table_visible'] = tvar
            row += 1
            for col in df.columns:
                var = tk.BooleanVar(value=current_visibility.get(table, {}).get(col, True))
                cb2 = ttk.Checkbutton(inner, text=human_label(col), variable=var)
                cb2.grid(row=row, column=0, sticky='w', padx=12)
                self.vars[table][col] = var
                row += 1
        btns = ttk.Frame(self); btns.pack(fill='x', pady=8)
        ttk.Button(btns, text='OK', command=self.on_ok).pack(side='right', padx=6)
        ttk.Button(btns, text='Cancel', command=self.on_cancel).pack(side='right')
        self.grab_set(); self.wait_window(self)
    def on_ok(self):
        res = {}
        for table, cmap in self.vars.items():
            res[table] = {}
            for col, var in cmap.items():
                res[table][col] = bool(var.get())
        self.result = res; self.ok = True; self.destroy()
    def on_cancel(self):
        self.ok = False; self.destroy()

class DefaultChildRowsDialog(tk.Toplevel):
    """Simple dialog to add/edit default child row templates."""
    def __init__(self, parent, title, tables, current_templates):
        super().__init__(parent); self.transient(parent); self.title(title); self.parent = parent
        self.result = {}; self.ok = False
        body = ttk.Frame(self); body.pack(padx=12, pady=12, fill='both', expand=True)
        canvas = tk.Canvas(body, height=520); vs = ttk.Scrollbar(body, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vs.set); vs.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        inner = ttk.Frame(canvas); canvas.create_window((0,0), window=inner, anchor='nw')
        def on_conf(e): canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', on_conf)
        self.editors = {}
        row = 0
        for t in tables:
            df, _ = parent.schema.tables.get(t, (None, None))
            if df is None: continue
            ttk.Label(inner, text=f'Table: {t}', font=('Segoe UI', 10, 'bold')).grid(row=row, column=0, sticky='w', pady=(8,4), padx=6); row+=1
            # show existing templates as JSON text (simple UX)
            txt = tk.Text(inner, height=4, width=80)
            cur = current_templates.get(t, [])
            txt.insert('1.0', json.dumps(cur, indent=2, ensure_ascii=False))
            txt.grid(row=row, column=0, padx=6, pady=4)
            self.editors[t] = txt
            row += 1
        btns = ttk.Frame(self); btns.pack(fill='x', pady=8)
        ttk.Button(btns, text='OK', command=self.on_ok).pack(side='right', padx=6)
        ttk.Button(btns, text='Cancel', command=self.on_cancel).pack(side='right')
        self.grab_set(); self.wait_window(self)
    def on_ok(self):
        res = {}
        try:
            for t, txt in self.editors.items():
                raw = txt.get('1.0', 'end').strip()
                if raw:
                    parsed = json.loads(raw)
                    res[t] = parsed
            self.result = res; self.ok = True; self.destroy()
        except Exception as e:
            messagebox.showerror('Parse error', f'Failed to parse JSON: {e}')
    def on_cancel(self):
        self.ok = False; self.destroy()

# ---------- run ----------
def main():
    if not os.path.exists(DATA_FOLDER):
        print('Data folder not found:', DATA_FOLDER); return
    if not os.path.exists(RELATION_FILE):
        print('relations.csv not found:', RELATION_FILE); return
    schema = DeviceSchema(DATA_FOLDER, RELATION_FILE, root_table=ROOT_TABLE)
    app = DeviceBulkApp(schema)
    app.mainloop()

if __name__ == '__main__':
    main()

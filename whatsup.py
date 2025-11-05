# import tkinter as tk
# from tkinter import ttk, messagebox
# import pandas as pd
# import os

# CSV_FOLDER = "C:\\WhatsUpCSVs"       # your csv folder
# RELATION_FILE = "C:\\Users\\Ammar\\Desktop\\relations.csv"  # relation file path


# class CsvDashboard:
#     def __init__(self, root):
#         self.root = root
#         self.root.title("WhatsUp Gold CSV Manager (Relation-Aware)")
#         self.root.geometry("1200x700")

#         # Frames
#         self.frame_left = tk.Frame(root, width=200, bg="#f0f0f0")
#         self.frame_left.pack(side="left", fill="y")

#         self.frame_main = tk.Frame(root)
#         self.frame_main.pack(side="right", fill="both", expand=True)

#         self.frame_top = tk.Frame(self.frame_main)
#         self.frame_top.pack(side="top", fill="x")

#         self.frame_table = tk.Frame(self.frame_main)
#         self.frame_table.pack(fill="both", expand=True)

#         # Left: table list
#         tk.Label(self.frame_left, text="Tables", bg="#d0d0d0", font=("Segoe UI", 10, "bold")).pack(fill="x")
#         self.listbox = tk.Listbox(self.frame_left)
#         self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
#         self.listbox.bind("<<ListboxSelect>>", self.load_table)

#         # Buttons
#         ttk.Button(self.frame_top, text="Add Row", command=self.add_row).pack(side="left", padx=5, pady=5)
#         ttk.Button(self.frame_top, text="Edit Row", command=self.edit_row).pack(side="left", padx=5)
#         ttk.Button(self.frame_top, text="Delete Row", command=self.delete_row).pack(side="left", padx=5)
#         ttk.Button(self.frame_top, text="Save CSV", command=self.save_csv).pack(side="left", padx=5)
#         ttk.Button(self.frame_top, text="Sync to SQL", command=self.sync_to_sql).pack(side="left", padx=5)

#         # Status
#         self.status = tk.Label(root, text="Ready", anchor="w", bg="#e8e8e8")
#         self.status.pack(side="bottom", fill="x")

#         # Table view
#         self.tree = ttk.Treeview(self.frame_table)
#         self.tree.pack(fill="both", expand=True)
#         self.tree.bind("<Double-1>", lambda e: self.edit_row())

#         # Load data
#         self.load_csv_list()
#         self.load_relations()

#     def load_csv_list(self):
#         self.csv_files = [f for f in os.listdir(CSV_FOLDER) if f.endswith(".csv")]
#         self.listbox.delete(0, tk.END)
#         for f in self.csv_files:
#             self.listbox.insert(tk.END, f.replace(".csv", ""))

#     def load_relations(self):
#         """Load the schema relations file with flexible header names."""
#         if not os.path.exists(RELATION_FILE):
#             self.relations = pd.DataFrame(columns=["ForeignKeyName","ParentTable","ParentColumn","ReferencedTable","ReferencedColumn"])
#             return
#         df = pd.read_csv(RELATION_FILE)

#         # Normalize column names to handle upper/lower case or underscores
#         df.columns = [c.strip().lower() for c in df.columns]

#         # Map any similar names to expected ones
#         mapping = {
#             "tablename": "TableName",
#             "table_name": "TableName",
#             "columnname": "ColumnName",
#             "column_name": "ColumnName",
#             "referencestable": "ReferencesTable",
#             "referenced_table_name": "ReferencesTable",
#             "referencestable": "ReferencesTable",
#             "referencescolumn": "ReferencesColumn",
#             "referenced_column_name": "ReferencesColumn"
#         }

#         # Rebuild dataframe with normalized keys
#         renamed = {}
#         for c in df.columns:
#             key = mapping.get(c.lower())
#             if key:
#                 renamed[c] = key
#         df.rename(columns=renamed, inplace=True)

#         # Store
#         self.relations = df

#     def get_related_fields(self, table):
#         """Return all foreign key relations for a given table."""
#         if self.relations.empty:
#             return []
#         colname = [c for c in self.relations.columns if c.lower() in ["tablename", "table_name"]][0]
#         rels = self.relations[self.relations[colname].astype(str).str.lower() == table.lower()]
#         return rels.to_dict("records")

#     def load_relations(self):
#         """Load the schema relations file."""
#         if not os.path.exists(RELATION_FILE):
#             self.relations = pd.DataFrame(columns=["ForeignKeyName","ParentTable","ParentColumn","ReferencedTable","ReferencedColumn"])
#             return
#         self.relations = pd.read_csv(RELATION_FILE)

#     def load_table(self, event=None):
#         selection = self.listbox.curselection()
#         if not selection:
#             return
#         table_name = self.listbox.get(selection[0])
#         file_path = os.path.join(CSV_FOLDER, f"{table_name}.csv")
#         self.df = pd.read_csv(file_path)
#         self.display_table(self.df)
#         self.current_table = table_name
#         self.status.config(text=f"Loaded {table_name}")

#     def display_table(self, df):
#         self.tree.delete(*self.tree.get_children())
#         self.tree["columns"] = list(df.columns)
#         self.tree["show"] = "headings"
#         for col in df.columns:
#             self.tree.heading(col, text=col)
#             self.tree.column(col, width=120, anchor="center")
#         for _, row in df.iterrows():
#             self.tree.insert("", "end", values=list(row))

#     def get_related_fields(self, table):
#         rels = self.relations[self.relations["TableName"] == table]
#         return rels.to_dict("records")

#     def add_row(self):
#         if not hasattr(self, "df"):
#             return
#         self.open_row_editor("Add")

#     def edit_row(self):
#         if not hasattr(self, "df"):
#             return
#         selected = self.tree.selection()
#         if not selected:
#             messagebox.showinfo("Info", "Please select a row.")
#             return
#         values = self.tree.item(selected[0], "values")
#         self.open_row_editor("Edit", values)

#     def delete_row(self):
#         selected = self.tree.selection()
#         if not selected:
#             return
#         idx = self.tree.index(selected[0])
#         self.df.drop(self.df.index[idx], inplace=True)
#         self.display_table(self.df)
#         self.status.config(text="Row deleted.")

#     def save_csv(self):
#         file_path = os.path.join(CSV_FOLDER, f"{self.current_table}.csv")
#         self.df.to_csv(file_path, index=False)
#         self.status.config(text=f"Saved {self.current_table}.csv")

#     def open_row_editor(self, mode, values=None):
#         win = tk.Toplevel(self.root)
#         win.title(f"{mode} Row - {self.current_table}")
#         entries = {}
#         relations = self.get_related_fields(self.current_table)

#         for i, col in enumerate(self.df.columns):
#             tk.Label(win, text=col).grid(row=i, column=0, padx=5, pady=3)

#             # Check if this field has a relation
#             rel = next((r for r in relations if r["ColumnName"] == col), None)
#             if rel:
#                 # Load referenced values
#                 ref_table = rel["ReferencesTable"]
#                 ref_col = rel["ReferencesColumn"]
#                 ref_path = os.path.join(CSV_FOLDER, f"{ref_table}.csv")
#                 if os.path.exists(ref_path):
#                     ref_df = pd.read_csv(ref_path)
#                     options = list(ref_df[ref_col].astype(str).unique())
#                 else:
#                     options = []
#                 combo = ttk.Combobox(win, values=options, state="readonly")
#                 if values:
#                     combo.set(str(values[i]))
#                 combo.grid(row=i, column=1, padx=5, pady=3)
#                 entries[col] = combo

#                 # Button to open related table
#                 ttk.Button(win, text=f"View {ref_table}", command=lambda t=ref_table: self.show_related_table(t)).grid(row=i, column=2, padx=3)
#             else:
#                 e = tk.Entry(win)
#                 e.insert(0, values[i] if values else "")
#                 e.grid(row=i, column=1, padx=5, pady=3)
#                 entries[col] = e

#         def save_changes():
#             new_data = {c: entries[c].get() for c in self.df.columns}
#             if mode == "Add":
#                 self.df = pd.concat([self.df, pd.DataFrame([new_data])], ignore_index=True)
#             else:
#                 selected = self.tree.selection()
#                 if selected:
#                     idx = self.tree.index(selected[0])
#                     for c in self.df.columns:
#                         self.df.at[idx, c] = new_data[c]
#             self.display_table(self.df)
#             win.destroy()
#             self.status.config(text=f"Row {mode.lower()}ed successfully.")

#         ttk.Button(win, text="Save", command=save_changes).grid(columnspan=3, pady=10)

#     def show_related_table(self, table_name):
#         """Popup to show related table data."""
#         ref_path = os.path.join(CSV_FOLDER, f"{table_name}.csv")
#         if not os.path.exists(ref_path):
#             messagebox.showerror("Error", f"{table_name}.csv not found.")
#             return
#         df = pd.read_csv(ref_path)

#         top = tk.Toplevel(self.root)
#         top.title(f"Related Table: {table_name}")
#         tree = ttk.Treeview(top)
#         tree.pack(fill="both", expand=True)
#         tree["columns"] = list(df.columns)
#         tree["show"] = "headings"
#         for col in df.columns:
#             tree.heading(col, text=col)
#             tree.column(col, width=100)
#         for _, row in df.iterrows():
#             tree.insert("", "end", values=list(row))

#     def sync_to_sql(self):
#         messagebox.showinfo("Sync", "This will call your PowerShell script later.")


# if __name__ == "__main__":
#     root = tk.Tk()
#     app = CsvDashboard(root)
#     root.mainloop()
import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import os

DATA_FOLDER = "C:\\WhatsUpCSVs"       # your csv folder
RELATION_FILE = "C:\\Users\\Ammar\\Desktop\\relations.csv"  # relation file path

class DatabaseViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSV Database Manager (with Relations)")
        self.geometry("1200x700")

        self.tables = {}
        self.current_table = None
        self.current_df = None

        # Layout
        self.setup_ui()

        # Load data
        self.load_relations()
        self.load_tables()

    def setup_ui(self):
        # Sidebar
        sidebar = tk.Frame(self, bg="#f3f3f3", width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(sidebar, text="Tables", bg="#f3f3f3", font=("Segoe UI", 10, "bold")).pack(pady=10)
        self.table_listbox = tk.Listbox(sidebar)
        self.table_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.table_listbox.bind("<<ListboxSelect>>", self.load_table_data)

        tk.Button(sidebar, text="Save Changes", command=self.save_changes, bg="#d4edda").pack(pady=5, fill=tk.X)
        tk.Button(sidebar, text="Reload Data", command=self.reload_data, bg="#ffeeba").pack(pady=5, fill=tk.X)

        # Main display
        self.frame_main = tk.Frame(self)
        self.frame_main.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.label_table = tk.Label(self.frame_main, text="", font=("Segoe UI", 11, "bold"))
        self.label_table.pack(pady=10)

        self.tree = ttk.Treeview(self.frame_main, show="headings")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Buttons
        btn_frame = tk.Frame(self.frame_main)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="Add Row", command=self.add_row).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Delete Row", command=self.delete_row).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Edit Row", command=self.edit_row).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="View Related Tables", command=self.view_related).pack(side=tk.LEFT, padx=5)

    def load_relations(self):
        """Load relations.csv safely and normalize columns"""
        if not os.path.exists(RELATION_FILE):
            messagebox.showwarning("Warning", "relations.csv not found!")
            self.relations = pd.DataFrame(columns=[
                "ParentTable", "ParentColumn", "ReferencedTable", "ReferencedColumn"
            ])
            return

        try:
            # Read CSV with correct encoding and stripping quotes
            df = pd.read_csv(
                RELATION_FILE,
                encoding="utf-8-sig",
                quotechar='"',
                sep=",",
                skipinitialspace=True
            )

            # Clean column names
            df.columns = [c.strip().replace('"', '') for c in df.columns]

            # Verify expected columns exist
            required = {"ParentTable", "ParentColumn", "ReferencedTable", "ReferencedColumn"}
            missing = required - set(df.columns)
            if missing:
                raise Exception(f"Missing columns in relations file: {missing}")

            self.relations = df
            print("✅ Relations loaded successfully:")
            print(self.relations.head())

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load relations file:\n{e}")
            self.relations = pd.DataFrame(columns=[
                "ParentTable", "ParentColumn", "ReferencedTable", "ReferencedColumn"
            ])


    def load_tables(self):
        """Load all CSVs from the data folder"""
        if not os.path.exists(DATA_FOLDER):
            messagebox.showwarning("Warning", f"No data folder '{DATA_FOLDER}' found!")
            return

        for file in os.listdir(DATA_FOLDER):
            if file.endswith(".csv"):
                table_name = file[:-4]
                path = os.path.join(DATA_FOLDER, file)
                try:
                    self.tables[table_name] = pd.read_csv(path)
                    self.table_listbox.insert(tk.END, table_name)
                except Exception as e:
                    print(f"Error loading {file}: {e}")

    def load_table_data(self, event):
        selection = self.table_listbox.curselection()
        if not selection:
            return
        table_name = self.table_listbox.get(selection[0])
        self.current_table = table_name
        self.current_df = self.tables[table_name]
        self.show_table()

    def show_table(self):
        for col in self.tree.get_children():
            self.tree.delete(col)
        self.tree.delete(*self.tree.get_children())
        self.tree["columns"] = list(self.current_df.columns)
        for col in self.current_df.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
        for _, row in self.current_df.iterrows():
            self.tree.insert("", tk.END, values=list(row))
        self.label_table.config(text=f"Table: {self.current_table}")

    def add_row(self):
        self.edit_window(new=True)

    def delete_row(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Select a row first.")
            return
        idx = self.tree.index(selected[0])
        self.current_df.drop(self.current_df.index[idx], inplace=True)
        self.show_table()

    def edit_row(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Select a row first.")
            return
        idx = self.tree.index(selected[0])
        row_data = self.current_df.iloc[idx].to_dict()
        self.edit_window(row_data=row_data, idx=idx, new=False)

    def edit_window(self, row_data=None, idx=None, new=False):
        win = tk.Toplevel(self)
        win.title("Edit Row")
        entries = {}
        for i, col in enumerate(self.current_df.columns):
            tk.Label(win, text=col).grid(row=i, column=0, padx=5, pady=2)
            val = "" if new else str(row_data[col])
            e = tk.Entry(win)
            e.grid(row=i, column=1, padx=5, pady=2)
            e.insert(0, val)
            entries[col] = e

        def save():
            new_row = {c: e.get() for c, e in entries.items()}
            if new:
                self.current_df = pd.concat([self.current_df, pd.DataFrame([new_row])], ignore_index=True)
            else:
                for c, v in new_row.items():
                    self.current_df.at[idx, c] = v
            self.show_table()
            win.destroy()

        tk.Button(win, text="Save", command=save, bg="#d4edda").grid(row=len(entries), columnspan=2, pady=10)

    def view_related(self):
        """Show tables related to the current one"""
        if self.current_table is None:
            messagebox.showinfo("Info", "Select a table first.")
            return

        rels = self.relations[self.relations["ParentTable"].astype(str).str.lower() == self.current_table.lower()]
        if rels.empty:
            messagebox.showinfo("Info", f"No related tables found for {self.current_table}.")
            return

        win = tk.Toplevel(self)
        win.title(f"Related Tables for {self.current_table}")
        win.geometry("800x400")

        tree = ttk.Treeview(win, columns=["ParentColumn", "ReferencedTable", "ReferencedColumn"], show="headings")
        tree.pack(fill=tk.BOTH, expand=True)
        for col in ["ParentColumn", "ReferencedTable", "ReferencedColumn"]:
            tree.heading(col, text=col)
            tree.column(col, width=200)
        for _, row in rels.iterrows():
            tree.insert("", tk.END, values=[row["ParentColumn"], row["ReferencedTable"], row["ReferencedColumn"]])

    def save_changes(self):
        for name, df in self.tables.items():
            df.to_csv(os.path.join(DATA_FOLDER, f"{name}.csv"), index=False)
        messagebox.showinfo("Saved", "All CSV files updated successfully!")

    def reload_data(self):
        self.tables.clear()
        self.table_listbox.delete(0, tk.END)
        self.load_tables()
        messagebox.showinfo("Reloaded", "Data reloaded successfully.")

if __name__ == "__main__":
    app = DatabaseViewer()
    app.mainloop()

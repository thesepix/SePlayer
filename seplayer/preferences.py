"""Einstellungen-Dialog (Preferences): Farbschema, Start-Verhalten, Lautstärke."""
import tkinter as tk
from tkinter import ttk

from . import theme


class PreferencesDialog(tk.Toplevel):
    def __init__(self, master, state, on_save):
        super().__init__(master)
        theme.style_toplevel(self)
        self.title("Einstellungen")
        self.geometry("420x240")
        self.transient(master)
        self.on_save = on_save

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Farbschema:").grid(row=0, column=0, sticky=tk.W, pady=6)
        self.theme_var = tk.StringVar(value=state.get("theme", "light"))
        ttk.Radiobutton(frm, text="Hell", value="light", variable=self.theme_var).grid(
            row=0, column=1, sticky=tk.W, padx=4)
        ttk.Radiobutton(frm, text="Dunkel", value="dark", variable=self.theme_var).grid(
            row=0, column=2, sticky=tk.W, padx=4)

        self.autoload_var = tk.BooleanVar(value=bool(state.get("autoload_last", True)))
        ttk.Checkbutton(frm, text="Beim Start zuletzt geöffneten Ordner laden",
                        variable=self.autoload_var).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=6)

        ttk.Label(frm, text="Start-Lautstärke:").grid(row=2, column=0, sticky=tk.W, pady=6)
        self.vol_var = tk.IntVar(value=int(state.get("volume", 70)))
        ttk.Scale(frm, from_=0, to=100, variable=self.vol_var, orient=tk.HORIZONTAL).grid(
            row=2, column=1, columnspan=2, sticky=tk.EW, pady=6)
        frm.columnconfigure(1, weight=1)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(buttons, text="Speichern", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 6))
        self.grab_set()

    def _save(self):
        self.on_save({
            "theme": self.theme_var.get(),
            "autoload_last": bool(self.autoload_var.get()),
            "volume": int(self.vol_var.get()),
        })
        self.destroy()

"""Such-Dialog (Strg+F): rekursive Suche ab einem Ordner; Doppelklick spielt den Treffer ab."""
import os
import tkinter as tk
from tkinter import filedialog, ttk

from . import tags as taglib
from . import theme

MAX_RESULTS = 500


class SearchDialog(tk.Toplevel):
    def __init__(self, root, app, base_folder):
        super().__init__(root)
        self.app = app
        self.title("Suchen")
        theme.style_toplevel(self)
        self._paths = []
        self._cancel = False
        self._searching = False
        self.geometry("680x520")

        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=(8, 4))
        ttk.Label(top, text="Suchbegriff:").pack(side=tk.LEFT)
        self.query_var = tk.StringVar()
        entry = ttk.Entry(top, textvariable=self.query_var, width=36)
        entry.pack(side=tk.LEFT, padx=(4, 6), fill=tk.X, expand=True)
        entry.bind("<Return>", lambda _e: self._start_search())
        entry.focus_set()
        ttk.Button(top, text="Suchen", command=self._start_search).pack(side=tk.LEFT)
        self.stop_btn = ttk.Button(top, text="Stop", command=self._stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(6, 0))

        row = ttk.Frame(self)
        row.pack(fill=tk.X, padx=8, pady=2)
        ttk.Label(row, text="Ordner:").pack(side=tk.LEFT)
        self.base_var = tk.StringVar(value=base_folder or "")
        ttk.Entry(row, textvariable=self.base_var).pack(side=tk.LEFT, padx=(4, 4), fill=tk.X, expand=True)
        ttk.Button(row, text="\u2026", width=3, command=self._pick_folder).pack(side=tk.LEFT)

        opts = ttk.Frame(self)
        opts.pack(fill=tk.X, padx=8, pady=2)
        self.scope_var = tk.StringVar(value="recursive")
        ttk.Radiobutton(opts, text="Rekursiv durchsuchen", variable=self.scope_var,
                        value="recursive").pack(side=tk.LEFT)
        ttk.Radiobutton(opts, text="Nur direkt im Ordner", variable=self.scope_var,
                        value="flat").pack(side=tk.LEFT, padx=(10, 0))
        self.tags_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Auch Tags (Titel/Interpret/Album/Genre)",
                        variable=self.tags_var).pack(side=tk.LEFT, padx=(14, 0))

        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.results = tk.Listbox(list_frame, height=18, activestyle="dotbox")
        scroll = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.results.yview)
        self.results.config(yscrollcommand=scroll.set)
        self.results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        try:
            theme.style_tk_widget(self.results)
        except Exception:
            pass
        self.results.bind("<Double-1>", self._on_open)
        self.results.bind("<Return>", self._on_open)

        self.status_var = tk.StringVar(value="Doppelklick auf einen Treffer l\u00e4dt den Ordner und spielt ab.")
        ttk.Label(self, textvariable=self.status_var).pack(fill=tk.X, padx=8, pady=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _pick_folder(self):
        path = filedialog.askdirectory(title="Suchordner w\u00e4hlen",
                                        initialdir=self.base_var.get() or None)
        if path:
            self.base_var.set(path)

    def _stop(self):
        self._cancel = True

    def _start_search(self):
        if self._searching:
            return
        base = self.base_var.get().strip()
        q = self.query_var.get().strip().lower()
        if not base or not os.path.isdir(base):
            self.status_var.set("Bitte einen g\u00fcltigen Ordner angeben.")
            return
        if not q:
            self.status_var.set("Bitte einen Suchbegriff eingeben.")
            return
        self._cancel = False
        self._searching = True
        self.stop_btn.config(state=tk.NORMAL)
        self.results.delete(0, tk.END)
        self._paths = []
        self.status_var.set("Suche l\u00e4uft \u2026")
        self.after(50, lambda: self._search(base, q))

    def _search(self, base, q):
        recursive = self.scope_var.get() == "recursive"
        use_tags = self.tags_var.get()
        count = 0
        try:
            for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
                if self._cancel:
                    break
                if os.name != "nt":
                    dirnames[:] = [d for d in dirnames if not d.startswith(".")]
                if not recursive:
                    dirnames[:] = []
                for fn in sorted(filenames):
                    if not taglib.is_audio_file(fn):
                        continue
                    full = os.path.join(dirpath, fn)
                    if q in fn.lower():
                        self._add(full, fn)
                        count += 1
                    elif use_tags:
                        try:
                            meta = taglib.read_metadata(full)
                        except Exception:
                            meta = None
                        if meta:
                            hay = " ".join(str(meta.get(k) or "")
                                           for k in ("title", "artist", "album", "genre")).lower()
                            if q in hay:
                                label = " - ".join(x for x in (meta.get("artist"),
                                                               meta.get("title")) if x) or fn
                                self._add(full, f"{label}  [{fn}]")
                                count += 1
                    if count >= MAX_RESULTS:
                        break
                if count >= MAX_RESULTS:
                    break
                if count and count % 25 == 0:
                    self.status_var.set(f"Suche l\u00e4uft \u2026 bisher {count} Treffer")
                    self.update_idletasks()
        except OSError:
            pass
        self._searching = False
        self.stop_btn.config(state=tk.DISABLED)
        suffix = " (abgebrochen)" if self._cancel else ""
        self.status_var.set(f"{count} Treffer{suffix} \u2014 Doppelklick spielt ab")

    def _add(self, path, label):
        self._paths.append(path)
        self.results.insert(tk.END, label or os.path.basename(path))

    def _on_open(self, _event):
        sel = self.results.curselection()
        if sel and 0 <= sel[0] < len(self._paths):
            self.app.goto_track(self._paths[sel[0]], play=True)

    def _on_close(self):
        self._cancel = True
        self.destroy()

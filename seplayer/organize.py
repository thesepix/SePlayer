"""Auto-Organize: ausgewählte Dateien per Muster aus ihren Tags umbenennen (wie MediaMonkey)."""
import contextlib
import os
import time
import tkinter as tk
from tkinter import messagebox, ttk

from . import theme
from .util import apply_filename_pattern

DEFAULT_PATTERN = "## - artist - title"


class AutoOrganizeDialog(tk.Toplevel):
    def __init__(self, master, tracks, on_done=None, guard=None):
        super().__init__(master)
        theme.style_toplevel(self)
        self.tracks = tracks
        self.on_done = on_done
        self.guard = guard or contextlib.nullcontext
        self.title(f"Auto-Organize — {len(tracks)} Datei(en) umbenennen")
        self.geometry("720x460")
        self.transient(master)

        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Muster:").pack(side=tk.LEFT)
        self.pattern_var = tk.StringVar(value=DEFAULT_PATTERN)
        entry = ttk.Entry(top, textvariable=self.pattern_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        entry.bind("<KeyRelease>", lambda _e: self._refresh_preview())
        ttk.Label(top, text="## = Track-Nr. zweistellig, # = Track-Nr., <feld> oder Feldname = Tag-Wert"
                  ).pack(side=tk.LEFT, padx=6)

        self.preview = tk.Listbox(self, font=("TkDefaultFont", 9))
        theme.style_tk_widget(self.preview)
        self.preview.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(buttons, text="Umbenennen", command=self._do_rename).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 6))

        self._refresh_preview()
        self.grab_set()

    def _planned_names(self):
        planned = []
        for i, track in enumerate(self.tracks):
            base = apply_filename_pattern(self.pattern_var.get(), track, i + 1)
            ext = os.path.splitext(track["path"])[1]
            planned.append((track, base + ext if base else ""))
        return planned

    def _refresh_preview(self):
        self.preview.delete(0, tk.END)
        for track, new_name in self._planned_names():
            self.preview.insert(tk.END, f"{track['filename']}  ->  {new_name or '(unverändert)'}")

    def _do_rename(self):
        renamed, skipped, errors = [], [], []
        for i, (track, new_name) in enumerate(self._planned_names()):
            if not new_name:
                skipped.append(track["filename"])
                continue
            folder = os.path.dirname(track["path"])
            target = os.path.join(folder, new_name)
            if os.path.abspath(target) == os.path.abspath(track["path"]):
                skipped.append(track["filename"])
                continue
            ext = os.path.splitext(new_name)[1]
            base = new_name[:-len(ext)] if ext else new_name
            n = 1
            while os.path.exists(target):
                target = os.path.join(folder, f"{base} ({n}){ext}")
                n += 1
            try:
                with self.guard(track["path"]):
                    for attempt in range(3):
                        try:
                            os.rename(track["path"], target)
                            break
                        except OSError as exc:
                            # WinError 32/183: noch gesperrt -> kurzer Retry
                            if getattr(exc, "winerror", None) in (32, 183) and attempt < 2:
                                time.sleep(0.3)
                                continue
                            raise
            except OSError as exc:
                errors.append(f"{track['filename']}: {exc}")
                continue
            track["path"] = target
            track["filename"] = os.path.basename(target)
            renamed.append(f"{os.path.basename(target)}")
        if self.on_done:
            self.on_done()
        msg = f"{len(renamed)} Datei(en) umbenannt."
        if skipped:
            msg += f"\n{len(skipped)} unverändert/übersprungen."
        if errors:
            msg += "\n\nFehler:\n" + "\n".join(errors[:10])
        if errors:
            messagebox.showerror("Auto-Organize", msg, parent=self)
        else:
            messagebox.showinfo("Auto-Organize", msg, parent=self)
        self.destroy()

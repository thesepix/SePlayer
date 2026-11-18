"""Eigenschaften-Dialog: alle Tags eines Tracks ansehen und bearbeiten (Reiter wie bei MediaMonkey)."""
import tkinter as tk
from tkinter import messagebox, ttk

from . import tags as taglib
from .util import format_size, format_time, stars_text

EDIT_FIELDS = [
    ("title", "Titel"), ("artist", "Interpret"), ("album", "Album"),
    ("albumartist", "Albuminterpret"), ("composer", "Komponist"),
    ("genre", "Genre"), ("year", "Jahr"), ("track", "Track"), ("disc", "Disc"),
    ("comment", "Kommentar"),
]

RATING_WRITE_HINT = (
    "Beim Speichern wird die Bewertung in alle bekannten Felder geschrieben:\n"
    "MP3: POPM (POPULARIMETER) + TXXX „RATING MM“  ·  FLAC/OGG: RATING, RATING WMP, FMPS_RATING"
)


class PropertiesDialog(tk.Toplevel):
    def __init__(self, master, track, on_save=None):
        super().__init__(master)
        self.track = track
        self.on_save = on_save
        self.title(f"Eigenschaften — {track['filename']}")
        self.geometry("580x560")
        self.transient(master)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        tags_frame = ttk.Frame(notebook, padding=8)
        notebook.add(tags_frame, text="Tags")
        self.entries = {}
        for row, (key, label) in enumerate(EDIT_FIELDS):
            ttk.Label(tags_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar(value=track.get(key, ""))
            ttk.Entry(tags_frame, textvariable=var, width=52).grid(
                row=row, column=1, sticky=tk.EW, pady=2, padx=(8, 0))
            self.entries[key] = var
        tags_frame.columnconfigure(1, weight=1)
        row = len(EDIT_FIELDS)
        ttk.Label(tags_frame, text="Bewertung").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.rating_var = tk.IntVar(value=int(track.get("rating", 0)))
        rating_box = ttk.Frame(tags_frame)
        for stars in range(6):
            text = stars_text(stars) if stars else "keine"
            ttk.Radiobutton(rating_box, text=text, value=stars,
                            variable=self.rating_var).pack(side=tk.LEFT, padx=3)
        rating_box.grid(row=row, column=1, sticky=tk.W, padx=(8, 0))

        details = ttk.Frame(notebook, padding=8)
        notebook.add(details, text="Details")
        info_rows = [
            ("Datei", track["filename"]),
            ("Pfad", track["path"]),
            ("Größe", format_size(track.get("size", 0))),
            ("Format", track["ext"].upper()),
            ("Bitrate", f"{track['bitrate']} kbps" if track.get("bitrate") else "–"),
            ("Samplerate", f"{track['sample_rate']} Hz" if track.get("sample_rate") else "–"),
            ("Kanäle", str(track.get("channels")) if track.get("channels") else "–"),
            ("Dauer", format_time(track.get("duration", 0.0))),
        ]
        for r, (key, value) in enumerate(info_rows):
            ttk.Label(details, text=key, width=14, anchor=tk.W).grid(row=r, column=0, sticky=tk.W, pady=2)
            ttk.Label(details, text=value, anchor=tk.W, wraplength=420).grid(
                row=r, column=1, sticky=tk.W, pady=2, padx=(8, 0))
        details.columnconfigure(1, weight=1)

        rating_frame = ttk.Frame(notebook, padding=8)
        notebook.add(rating_frame, text="Bewertungsfelder")
        fields = taglib.read_rating_fields(track["path"])
        if fields:
            for r, (name, stars) in enumerate(fields.items()):
                ttk.Label(rating_frame, text=name, width=24, anchor=tk.W).grid(
                    row=r, column=0, sticky=tk.W, pady=2)
                ttk.Label(rating_frame, text=stars_text(stars) if stars else "keine").grid(
                    row=r, column=1, sticky=tk.W, pady=2, padx=(8, 0))
        else:
            ttk.Label(rating_frame, text="In dieser Datei sind keine Bewertungsfelder gesetzt.").grid(
                row=0, column=0, sticky=tk.W)
        ttk.Label(rating_frame, text=RATING_WRITE_HINT, wraplength=500, justify=tk.LEFT).grid(
            row=10, column=0, columnspan=2, sticky=tk.W, pady=(14, 0))

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(buttons, text="Speichern", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 6))
        self.grab_set()

    def _save(self):
        fields = {key: var.get().strip() for key, var in self.entries.items()}
        ok_meta = taglib.write_metadata(self.track["path"], fields)
        ok_rating = taglib.write_rating(self.track["path"], int(self.rating_var.get()))
        if not (ok_meta and ok_rating):
            messagebox.showerror(
                "Fehler", "Nicht alle Felder konnten in die Datei geschrieben werden.", parent=self)
            return
        self.track.update(fields)
        self.track["rating"] = int(self.rating_var.get())
        if self.on_save:
            self.on_save(self.track)
        self.destroy()

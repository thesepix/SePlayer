"""Eigenschaften-Dialog: Tags, Details, Bewertungsfelder und Cover ansehen/bearbeiten (Reiter wie bei MediaMonkey)."""
import contextlib
import io
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image

from . import tags as taglib
from . import theme
from .util import format_size, format_time, stars_text

EDIT_FIELDS = [
    ("title", "Titel"), ("artist", "Interpret"), ("album", "Album"),
    ("albumartist", "Albuminterpret"), ("composer", "Komponist"),
    ("genre", "Genre"), ("year", "Jahr"), ("track", "Track"), ("disc", "Disc"),
    ("comment", "Kommentar"),
]

def plan_save(tracks, field_values, prefill, stars, prefill_stars):
    """Entscheidet, was beim Speichern geschrieben wird.

    Einzel-Track: alles. Mehrfachauswahl: nur Felder, die sich vom gemeinsamen
    Vorbelegungs-Wert unterscheiden (leer vorbefüllt = unverändert lassen)."""
    multi = len(tracks) > 1
    fields = {}
    for key, value in field_values.items():
        if not multi or value != prefill.get(key, ""):
            fields[key] = value
    write_rating = (not multi) or stars != prefill_stars
    return fields, write_rating


RATING_WRITE_HINT = (
    "Beim Speichern wird die Bewertung in alle bekannten Felder geschrieben:\n"
    "MP3: POPM (POPULARIMETER) + TXXX „RATING MM“  ·  FLAC/OGG: RATING, RATING WMP, FMPS_RATING"
)

COVER_MAX = 256


class PropertiesDialog(tk.Toplevel):
    """tracks: Liste der ausgewählten Tracks (Mehrfachauswahl möglich)."""

    def __init__(self, master, tracks, on_save=None, guard=None):
        super().__init__(master)
        theme.style_toplevel(self)
        self.tracks = tracks
        self.on_save = on_save
        self.guard = guard or contextlib.nullcontext
        self._cover_photo = None
        track = tracks[0]
        if len(tracks) == 1:
            self.title(f"Eigenschaften — {track['filename']}")
        else:
            self.title(f"Eigenschaften — {len(tracks)} Dateien")
        self.geometry("580x600")
        self.transient(master)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        tags_frame = ttk.Frame(notebook, padding=8)
        notebook.add(tags_frame, text="Tags")
        self.prefill = {}
        for key, _label in EDIT_FIELDS:
            values = {t.get(key, "") for t in tracks}
            self.prefill[key] = track.get(key, "") if len(values) == 1 else ""
        rating_values = {int(t.get("rating", 0)) for t in tracks}
        self.prefill_stars = int(track.get("rating", 0)) if len(rating_values) == 1 else 0
        if len(tracks) > 1:
            ttk.Label(tags_frame,
                      text=f"{len(tracks)} Dateien: Felder mit gleichem Wert sind vorbefüllt, "
                           f"unterschiedliche leer (leer lassen = nicht ändern).").grid(
                row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
        self.entries = {}
        for row, (key, label) in enumerate(EDIT_FIELDS, start=1 if len(tracks) > 1 else 0):
            ttk.Label(tags_frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=2)
            var = tk.StringVar(value=self.prefill[key])
            ttk.Entry(tags_frame, textvariable=var, width=52).grid(
                row=row, column=1, sticky=tk.EW, pady=2, padx=(8, 0))
            self.entries[key] = var
        tags_frame.columnconfigure(1, weight=1)
        row = len(EDIT_FIELDS) + (1 if len(tracks) > 1 else 0)
        ttk.Label(tags_frame, text="Bewertung").grid(row=row, column=0, sticky=tk.W, pady=2)
        self.rating_var = tk.IntVar(value=self.prefill_stars)
        rating_box = ttk.Frame(tags_frame)
        for stars in range(6):
            text = stars_text(stars) if stars else "keine"
            ttk.Radiobutton(rating_box, text=text, value=stars,
                            variable=self.rating_var).pack(side=tk.LEFT, padx=3)
        rating_box.grid(row=row, column=1, sticky=tk.W, padx=(8, 0))

        details = ttk.Frame(notebook, padding=8)
        notebook.add(details, text="Details")
        info_rows = [
            ("Datei", track["filename"] + (f"  (+ {len(tracks) - 1} weitere)" if len(tracks) > 1 else "")),
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

        cover_frame = ttk.Frame(notebook, padding=8)
        notebook.add(cover_frame, text="Cover")
        self.cover_label = ttk.Label(cover_frame, text="Kein Cover vorhanden", anchor=tk.CENTER)
        self.cover_label.pack(pady=6)
        cover_btns = ttk.Frame(cover_frame)
        cover_btns.pack(pady=4)
        ttk.Button(cover_btns, text="Cover ersetzen …", command=self._pick_cover).pack(side=tk.LEFT, padx=3)
        ttk.Button(cover_btns, text="Cover entfernen", command=self._remove_cover).pack(side=tk.LEFT, padx=3)
        self._refresh_cover_tab()

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(buttons, text="Speichern", command=self._save).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 6))
        self.grab_set()

    # ---------- Cover-Reiter ----------

    def _refresh_cover_tab(self):
        data = taglib.read_cover(self.tracks[0]["path"])
        if not data:
            self._cover_photo = None
            self.cover_label.config(image="", text="Kein Cover vorhanden")
            return
        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
            image.thumbnail((COVER_MAX, COVER_MAX))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            self._cover_photo = tk.PhotoImage(data=buffer.getvalue())
            self.cover_label.config(image=self._cover_photo, text="")
        except Exception:
            self._cover_photo = None
            self.cover_label.config(image="", text="Cover konnte nicht angezeigt werden")

    def _pick_cover(self):
        path = filedialog.askopenfilename(
            parent=self, title="Cover-Bild wählen",
            filetypes=[("Bilder", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"), ("Alle Dateien", "*.*")])
        if not path:
            return
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            messagebox.showerror("Fehler", f"Bild nicht lesbar:\n{exc}", parent=self)
            return
        ext = os.path.splitext(path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp"}.get(ext, "image/png")
        failed = []
        for t in self.tracks:
            with self.guard(t["path"]):
                ok = taglib.write_cover(t["path"], data, mime)
            if not ok:
                failed.append(t["filename"])
        if failed:
            messagebox.showerror("Fehler", "Cover konnte nicht geschrieben werden bei:\n"
                                           + "\n".join(failed[:10])
                                           + (f"\n\nLetzter Fehler: {taglib.last_error}" if taglib.last_error else ""),
                                 parent=self)
        self._refresh_cover_tab()

    def _remove_cover(self):
        failed = []
        for t in self.tracks:
            with self.guard(t["path"]):
                ok = taglib.remove_cover(t["path"])
            if not ok:
                failed.append(t["filename"])
        if failed:
            messagebox.showerror("Fehler", "Cover konnte nicht entfernt werden bei:\n"
                                           + "\n".join(failed[:10])
                                           + (f"\n\nLetzter Fehler: {taglib.last_error}" if taglib.last_error else ""),
                                 parent=self)
        self._refresh_cover_tab()

    # ---------- Speichern ----------

    def _save(self):
        field_values = {key: var.get().strip() for key, var in self.entries.items()}
        stars = int(self.rating_var.get())
        fields, write_rating = plan_save(self.tracks, field_values, self.prefill, stars, self.prefill_stars)
        failed = []
        for track in self.tracks:
            ok_meta = ok_rating = True
            if fields or write_rating:
                with self.guard(track["path"]):
                    if fields:
                        ok_meta = taglib.write_metadata(track["path"], fields)
                    if write_rating:
                        ok_rating = taglib.write_rating(track["path"], stars)
            if not (ok_meta and ok_rating):
                failed.append(track["filename"])
                continue
            track.update(fields)
            if write_rating:
                track["rating"] = stars
            if self.on_save:
                self.on_save(track)
        if failed:
            messagebox.showerror(
                "Fehler",
                f"Bei {len(failed)} Datei(en) konnten nicht alle Felder gespeichert werden:\n"
                + "\n".join(failed[:10])
                + (f"\n\nLetzter Fehler: {taglib.last_error}" if taglib.last_error else ""),
                parent=self)
            return
        self.destroy()

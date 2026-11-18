"""Grafische Oberfläche des SePlayer (tkinter, läuft auf Windows, macOS und Linux).

Layout:
  links oben   -> Favoriten + Ordner-Baum (Dateisystem)
  links unten  -> Cover des ausgewählten Albums
  Mitte        -> Audiodateien des gewählten Ordners (konfigurierbare Spalten mit Tags)
  Mitte unten  -> Player-Leiste (Play/Pause/Stop, Vor/Zurück, Fortschritt, Lautstärke)

Zustand (Fenstergröße, Sash-Positionen, letzter Ordner, Favoriten, Spalten) wird
in state.json gespeichert und beim nächsten Start wiederhergestellt.
"""
import io
import os
import string
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pygame
from PIL import Image

from . import state as statelib
from . import tags as taglib
from .audio import PlaybackEngine
from .properties import PropertiesDialog
from .util import format_size, format_time, stars_text

POLL_MS = 200
COVER_MAX = 240

FIELD_DEFS = [
    ("nr", "Nr.", 40), ("title", "Titel", 240), ("artist", "Interpret", 160),
    ("album", "Album", 160), ("rating", "Bewertung", 90), ("duration", "Dauer", 60),
    ("bitrate", "Bitrate", 80), ("genre", "Genre", 110), ("year", "Jahr", 50),
    ("comment", "Kommentar", 170), ("size", "Größe", 80), ("format", "Format", 110),
    ("filename", "Datei", 200), ("path", "Pfad", 260),
]
FIELD_LABELS = {fid: label for fid, label, _w in FIELD_DEFS}
DEFAULT_COLUMNS = ["nr", "title", "artist", "album", "rating", "duration", "format"]
CENTER_ANCHOR = {"nr", "duration", "year", "rating", "bitrate", "size"}

SORT_KEYS = {
    "nr": lambda t: (int(t["track"]) if t["track"].isdigit() else 999, t["title"].lower()),
    "title": lambda t: t["title"].lower(),
    "artist": lambda t: t["artist"].lower(),
    "album": lambda t: t["album"].lower(),
    "rating": lambda t: t["rating"],
    "duration": lambda t: t["duration"],
    "bitrate": lambda t: t["bitrate"],
    "genre": lambda t: t["genre"].lower(),
    "year": lambda t: t["year"],
    "comment": lambda t: t["comment"].lower(),
    "size": lambda t: t["size"],
    "format": lambda t: t["ext"],
    "filename": lambda t: t["filename"].lower(),
    "path": lambda t: t["path"].lower(),
}


def default_column_config():
    return [{"id": fid, "visible": fid in DEFAULT_COLUMNS, "width": w}
            for fid, _label, w in FIELD_DEFS]


class ColumnDialog(tk.Toplevel):
    """Spalten konfigurieren: sichtbar ja/nein, Reihenfolge, Breite."""

    def __init__(self, master, config, on_ok):
        super().__init__(master)
        self.title("Spalten anpassen")
        self.geometry("420x420")
        self.transient(master)
        self.on_ok = on_ok
        self.config = [dict(c) for c in config]

        self.tree = ttk.Treeview(self, columns=("sel", "name", "width"), show="headings", height=14)
        self.tree.heading("sel", text="●")
        self.tree.heading("name", text="Feld")
        self.tree.heading("width", text="Breite")
        self.tree.column("sel", width=30, anchor=tk.CENTER, stretch=False)
        self.tree.column("name", width=200, stretch=True)
        self.tree.column("width", width=80, anchor=tk.E, stretch=False)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.tree.bind("<Button-1>", self._on_click)
        self._refresh()

        row = ttk.Frame(self)
        row.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(row, text="▲", width=3, command=lambda: self._move(-1)).pack(side=tk.LEFT)
        ttk.Button(row, text="▼", width=3, command=lambda: self._move(1)).pack(side=tk.LEFT, padx=2)
        ttk.Label(row, text="Breite:").pack(side=tk.LEFT, padx=(10, 2))
        self.width_var = tk.StringVar(value="120")
        ttk.Spinbox(row, from_=30, to=800, textvariable=self.width_var, width=6).pack(side=tk.LEFT)
        ttk.Button(row, text="Breite setzen", command=self._set_width).pack(side=tk.LEFT, padx=4)
        ttk.Button(row, text="OK", command=self._ok).pack(side=tk.RIGHT)
        ttk.Button(row, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 6))
        self.grab_set()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for i, col in enumerate(self.config):
            self.tree.insert("", "end", iid=str(i),
                             values=("☑" if col["visible"] else "☐",
                                     FIELD_LABELS.get(col["id"], col["id"]), col["width"]))

    def _selected(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _on_click(self, event):
        if self.tree.identify_column(event.x) != "#1":
            return
        item = self.tree.identify_row(event.y)
        if not item:
            return
        i = int(item)
        self.config[i]["visible"] = not self.config[i]["visible"]
        self._refresh()
        self.tree.selection_set(str(i))

    def _move(self, delta):
        i = self._selected()
        if i is None:
            return
        j = i + delta
        if 0 <= j < len(self.config):
            self.config[i], self.config[j] = self.config[j], self.config[i]
            self._refresh()
            self.tree.selection_set(str(j))

    def _set_width(self):
        i = self._selected()
        if i is None:
            return
        try:
            self.config[i]["width"] = max(30, int(self.width_var.get()))
        except ValueError:
            return
        self._refresh()
        self.tree.selection_set(str(i))

    def _ok(self):
        self.on_ok(self.config)
        self.destroy()


class SePlayerApp:
    def __init__(self, root):
        self.root = root
        self._state = statelib.load_state()
        root.title("SePlayer")
        root.geometry(self._state.get("geometry") or "1100x680")
        root.minsize(860, 540)

        self.engine = PlaybackEngine(volume=0.7)
        self.folder = None
        self.tracks = []
        self.current_index = -1
        self.seeking = False
        self._sort_column = "nr"
        self._sort_reverse = False
        self._cover_cache = {}
        self._cover_photo = None

        cols = self._state.get("columns")
        self.column_config = cols if cols else default_column_config()
        self.favorites = [f for f in (self._state.get("favorites") or []) if os.path.isdir(f)]

        self._build_menu()
        self._build_widgets()
        self._build_tree_roots()
        self._bind_events()
        self._refresh_favorites()
        self.root.after(150, self._apply_layout)
        last = self._state.get("last_folder") or ""
        if last and os.path.isdir(last):
            self.root.after(250, lambda: self._select_path_in_tree(last))
        self._tick()

    # ---------- Persistenz ----------

    def _save_state(self):
        try:
            self._state["geometry"] = self.root.wm_geometry()
            self._state["sash_main"] = int(self.main_pane.sashpos(0))
            self._state["sash_left"] = int(self.left_pane.sashpos(0))
        except Exception:
            pass
        self._state["last_folder"] = self.folder or ""
        self._state["favorites"] = self.favorites
        self._state["columns"] = self.column_config
        statelib.save_state(self._state)

    def _on_close(self):
        self._save_state()
        self.root.destroy()

    def _apply_layout(self):
        try:
            self.main_pane.sashpos(0, int(self._state.get("sash_main", 300)))
            self.left_pane.sashpos(0, int(self._state.get("sash_left", 400)))
        except Exception:
            pass

    # ---------- Aufbau ----------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Ordner öffnen …", command=self._ask_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self._on_close)
        menubar.add_cascade(label="Datei", menu=file_menu)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Spalten anpassen …", command=self._open_column_dialog)
        view_menu.add_command(label="Aktuellen Ordner als Favorit pinnen", command=self._fav_add)
        menubar.add_cascade(label="Ansicht", menu=view_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Über", command=lambda: messagebox.showinfo(
            "Über SePlayer",
            "SePlayer\n\nDesktop-Player für MP3, FLAC, OGG, WAV u. a.\n"
            "Ordner-Navigation & Favoriten, konfigurierbare Spalten, Tags bearbeiten,\n"
            "Sternebewertungen in mehreren Rating-Feldern (POPM, RATING MM, RATING, RATING WMP …), Album-Cover."))
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        self.root.config(menu=menubar)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_widgets(self):
        self.main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(self.main_pane)
        self.main_pane.add(left, weight=1)
        self.left_pane = ttk.PanedWindow(left, orient=tk.VERTICAL)
        self.left_pane.pack(fill=tk.BOTH, expand=True)

        fav_frame = ttk.LabelFrame(self.left_pane, text="Favoriten")
        self.fav_list = tk.Listbox(fav_frame, height=4, activestyle="dotbox")
        fav_scroll = ttk.Scrollbar(fav_frame, orient=tk.VERTICAL, command=self.fav_list.yview)
        self.fav_list.configure(yscrollcommand=fav_scroll.set)
        self.fav_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fav_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        fav_btns = ttk.Frame(fav_frame)
        fav_btns.pack(fill=tk.X)
        ttk.Button(fav_btns, text="+ pin", width=6, command=self._fav_add).pack(side=tk.LEFT)
        ttk.Button(fav_btns, text="– entfernen", width=10, command=self._fav_remove).pack(side=tk.LEFT, padx=2)
        self.left_pane.add(fav_frame, weight=0)

        tree_frame = ttk.LabelFrame(self.left_pane, text="Ordner")
        self.tree = ttk.Treeview(tree_frame, show="tree")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_pane.add(tree_frame, weight=3)

        cover_frame = ttk.LabelFrame(self.left_pane, text="Album-Cover")
        self.cover_label = ttk.Label(cover_frame, text="Kein Album ausgewählt", anchor=tk.CENTER)
        self.cover_label.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 2))
        self.album_label = ttk.Label(cover_frame, text="", anchor=tk.CENTER,
                                     justify=tk.CENTER, wraplength=260)
        self.album_label.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.left_pane.add(cover_frame, weight=2)

        right = ttk.Frame(self.main_pane)
        self.main_pane.add(right, weight=4)

        list_frame = ttk.LabelFrame(right, text="Dateien im Ordner")
        self.listbox = ttk.Treeview(list_frame, show="headings", selectmode="browse")
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))
        self._apply_columns()

        player = ttk.LabelFrame(right, text="Wiedergabe")
        player.pack(fill=tk.X, padx=4, pady=(2, 4))

        controls = ttk.Frame(player)
        controls.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(controls, text="⏮", width=3, command=self.play_previous).pack(side=tk.LEFT)
        self.play_button = ttk.Button(controls, text="▶", width=3, command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="⏹", width=3, command=self.stop).pack(side=tk.LEFT)
        ttk.Button(controls, text="⏭", width=3, command=self.play_next).pack(side=tk.LEFT, padx=2)
        self.track_label = ttk.Label(controls, text="–")
        self.track_label.pack(side=tk.LEFT, padx=12)

        seek_row = ttk.Frame(player)
        seek_row.pack(fill=tk.X, padx=6, pady=(0, 6))
        self.time_current = ttk.Label(seek_row, text="00:00", width=6)
        self.time_current.pack(side=tk.LEFT)
        self.progress = tk.Scale(seek_row, from_=0, to=1000, orient=tk.HORIZONTAL,
                                  showvalue=False, highlightthickness=0, bd=0,
                                  command=lambda _v: None)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        self.time_total = ttk.Label(seek_row, text="00:00", width=6)
        self.time_total.pack(side=tk.LEFT)
        ttk.Label(seek_row, text="🔊").pack(side=tk.LEFT, padx=(12, 2))
        self.volume = tk.Scale(seek_row, from_=100, to=0, orient=tk.HORIZONTAL, showvalue=False,
                               highlightthickness=0, bd=0, width=90, command=self._on_volume)
        self.volume.set(70)
        self.volume.pack(side=tk.LEFT)

    def _apply_columns(self):
        visible = [c for c in self.column_config if c["visible"]]
        self.listbox["columns"] = tuple(c["id"] for c in visible)
        for col in visible:
            fid = col["id"]
            self.listbox.heading(fid, text=FIELD_LABELS.get(fid, fid),
                                 command=lambda c=fid: self._sort_by(c))
            anchor = tk.CENTER if fid in CENTER_ANCHOR else tk.W
            self.listbox.column(fid, width=col["width"], stretch=True, anchor=anchor)
        self._fill_list()

    def _open_column_dialog(self):
        ColumnDialog(self.root, self.column_config, self._on_columns_changed)

    def _on_columns_changed(self, config):
        self.column_config = config
        self._apply_columns()
        self._save_state()

    def _build_tree_roots(self):
        if os.name == "nt":
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    self._insert_dir("", drive)
        else:
            self._insert_dir("", os.sep)
            home = os.path.expanduser("~")
            if os.path.abspath(home) != os.path.abspath(os.sep):
                self._insert_dir("", home)

    def _insert_dir(self, parent, path):
        name = os.path.basename(path.rstrip(os.sep)) or path
        node = self.tree.insert(parent, "end", text=name, values=(path,), open=False)
        self.tree.insert(node, "end", text="…", values=("",))
        return node

    def _bind_events(self):
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.fav_list.bind("<Double-Button-1>", self._on_fav_select)
        self.listbox.bind("<<TreeviewSelect>>", lambda _e: self._update_cover())
        self.listbox.bind("<Double-1>", self._on_double_click)
        self.listbox.bind("<Button-3>", self._on_right_click)
        self.listbox.bind("<Button-2>", self._on_right_click)  # macOS: rechte Taste = Button-2
        self.progress.bind("<ButtonPress-1>", lambda _e: setattr(self, "seeking", True))
        self.progress.bind("<ButtonRelease-1>", self._on_seek_release)
        self.root.bind("<space>", lambda _e: self.toggle_play())
        self.root.bind("<Right>", lambda _e: self.play_next())
        self.root.bind("<Left>", lambda _e: self.play_previous())

    # ---------- Favoriten ----------

    def _refresh_favorites(self):
        self.fav_list.delete(0, tk.END)
        for fav in self.favorites:
            self.fav_list.insert(tk.END, os.path.basename(fav.rstrip(os.sep)) or fav)

    def _fav_add(self):
        if self.folder and self.folder not in self.favorites:
            self.favorites.append(self.folder)
            self._refresh_favorites()
            self._save_state()

    def _fav_remove(self):
        sel = self.fav_list.curselection()
        if sel:
            del self.favorites[sel[0]]
            self._refresh_favorites()
            self._save_state()

    def _on_fav_select(self, _event):
        sel = self.fav_list.curselection()
        if sel and sel[0] < len(self.favorites):
            path = self.favorites[sel[0]]
            if os.path.isdir(path):
                self.load_folder(path)
                self._select_path_in_tree(path)

    # ---------- Ordner-Baum ----------

    def _populate_node(self, node, path):
        try:
            entries = sorted(os.listdir(path))
        except OSError:
            return False
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full) and not (os.name != "nt" and entry.startswith(".")):
                self._insert_dir(node, full)
        return True

    def _on_tree_open(self, _event):
        node = self.tree.focus()
        if not node and self.tree.selection():
            node = self.tree.selection()[0]
        if not node:
            return
        values = self.tree.item(node, "values")
        path = values[0] if values else ""
        if not path:
            return
        children = self.tree.get_children(node)
        if children and self.tree.item(children[0], "values")[0] == "":
            self.tree.delete(children[0])
            if not self._populate_node(node, path):
                self.tree.insert(node, "end", text="(kein Zugriff)", values=("",))

    def _find_child(self, node, path):
        for child in self.tree.get_children(node):
            values = self.tree.item(child, "values")
            if values and values[0] == path:
                return child
        return None

    def _select_path_in_tree(self, path):
        """Klappt den Baum bis `path` auf und wählt den Knoten aus (lädt dadurch den Ordner)."""
        path = os.path.abspath(path)
        best_node, best_path = None, ""
        for node in self.tree.get_children(""):
            values = self.tree.item(node, "values")
            root_path = values[0] if values else ""
            if root_path and (path == root_path
                              or path.startswith(root_path.rstrip(os.sep) + os.sep)):
                if len(root_path) > len(best_path):
                    best_node, best_path = node, root_path
        if best_node is None:
            return
        node, current = best_node, best_path
        self.tree.selection_set(node)
        rel = path[len(current.rstrip(os.sep)):].lstrip(os.sep)
        for part in (rel.split(os.sep) if rel else []):
            current = os.path.join(current, part)
            child = self._find_child(node, current)
            if child is None:
                child = self._insert_dir(node, current)
                children = self.tree.get_children(child)
                if children:
                    self.tree.delete(children[0])
                self._populate_node(child, current)
            self.tree.item(node, open=True)
            node = child
        self.tree.selection_set(node)
        self.tree.see(node)
        self.tree.focus(node)

    def _on_tree_select(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        path = values[0] if values else ""
        if path and os.path.isdir(path):
            self.load_folder(path)

    def _ask_folder(self):
        path = filedialog.askdirectory(title="Musikordner wählen")
        if path:
            self.load_folder(path)
            self._select_path_in_tree(path)

    # ---------- Dateiliste ----------

    def load_folder(self, path):
        self.folder = path
        self.tracks = []
        self.current_index = -1
        try:
            entries = sorted(os.listdir(path))
        except OSError as exc:
            messagebox.showerror("Fehler", f"Ordner nicht lesbar:\n{path}\n\n{exc}")
            return
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isfile(full) and taglib.is_audio_file(entry):
                meta = taglib.read_metadata(full)
                self.tracks.append(meta)
        self._sort_reverse = False
        self._sort_tracks()
        self._fill_list()
        self._update_cover()
        self._save_state()

    def _sort_tracks(self):
        self.tracks.sort(key=SORT_KEYS[self._sort_column], reverse=self._sort_reverse)

    def _sort_by(self, column):
        if self._sort_column == column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column
            self._sort_reverse = False
        self._sort_tracks()
        self._fill_list()
        if 0 <= self.current_index < len(self.tracks):
            self.listbox.selection_set(str(self.current_index))

    def _visible_column_ids(self):
        return [c["id"] for c in self.column_config if c["visible"]]

    def _row_dict(self, index):
        t = self.tracks[index]
        return {
            "nr": t["track"] or str(index + 1),
            "title": t["title"],
            "artist": t["artist"],
            "album": t["album"],
            "rating": stars_text(t["rating"]) if t["rating"] else "",
            "duration": format_time(t["duration"]),
            "bitrate": f"{t['bitrate']} kbps" if t["bitrate"] else "",
            "genre": t["genre"],
            "year": t["year"],
            "comment": t["comment"],
            "size": format_size(t["size"]),
            "format": t["ext"].upper() + (f" · {t['bitrate']} kbps" if t["bitrate"] else ""),
            "filename": t["filename"],
            "path": t["path"],
        }

    def _row_values(self, index):
        row = self._row_dict(index)
        return tuple(row.get(cid, "") for cid in self._visible_column_ids())

    def _fill_list(self):
        self.listbox.delete(*self.listbox.get_children())
        for i in range(len(self.tracks)):
            self.listbox.insert("", "end", iid=str(i), values=self._row_values(i))

    # ---------- Wiedergabe ----------

    def _selected_index(self):
        selection = self.listbox.selection()
        if selection:
            try:
                return int(selection[0])
            except ValueError:
                return -1
        return -1

    def _on_double_click(self, _event):
        index = self._selected_index()
        if index >= 0:
            self.play_index(index)

    def play_index(self, index):
        if not 0 <= index < len(self.tracks):
            return
        if not self.engine.available:
            messagebox.showwarning(
                "Kein Audio-Gerät",
                "Die Audiowiedergabe ist nicht verfügbar — der Audio-Mixer konnte nicht initialisiert werden.")
            return
        track = self.tracks[index]
        try:
            self.engine.load(track["path"])
            self.engine.play()
        except pygame.error as exc:
            messagebox.showwarning(
                "Wiedergabe nicht möglich",
                f"{track['filename']}\n\nDieses Format wird nicht unterstützt.\n({exc})")
            return
        self.current_index = index
        self.listbox.selection_set(str(index))
        self.listbox.see(str(index))
        self.listbox.focus(str(index))
        self.play_button.config(text="⏸")
        label = track["title"]
        if track["artist"]:
            label = f"{track['artist']} – {label}"
        self.track_label.config(text=label)
        self.time_total.config(text=format_time(track["duration"]))
        self._update_cover()

    def toggle_play(self):
        if not self.engine.available:
            messagebox.showwarning(
                "Kein Audio-Gerät",
                "Die Audiowiedergabe ist nicht verfügbar — der Audio-Mixer konnte nicht initialisiert werden.")
            return
        if self.engine.is_playing():
            self.engine.pause()
            self.play_button.config(text="▶")
        elif self.engine.paused and self.current_index >= 0:
            self.engine.resume()
            self.play_button.config(text="⏸")
        elif self.tracks:
            index = self._selected_index()
            if index < 0:
                index = self.current_index
            if index < 0:
                index = 0
            self.play_index(index)

    def stop(self):
        self.engine.stop()
        self.play_button.config(text="▶")
        self.progress.set(0)
        self.time_current.config(text="00:00")

    def play_next(self, auto=False):
        if not self.tracks:
            return
        nxt = self.current_index + 1
        if nxt >= len(self.tracks):
            if auto:
                self.stop()
                return
            nxt = 0
        self.play_index(nxt)

    def play_previous(self):
        if not self.tracks:
            return
        if self.engine.position() > 3:
            self.engine.seek(0)
            return
        prev = self.current_index - 1
        if prev < 0:
            prev = len(self.tracks) - 1
        self.play_index(prev)

    def _on_seek_release(self, _event):
        self.seeking = False
        if 0 <= self.current_index < len(self.tracks) and self.engine.current_path:
            duration = self.tracks[self.current_index]["duration"]
            if duration > 0:
                try:
                    self.engine.seek(self.progress.get() / 1000.0 * duration)
                    self.play_button.config(text="⏸")
                except pygame.error:
                    pass

    def _on_volume(self, value):
        self.engine.set_volume(float(value) / 100.0)

    # ---------- Cover ----------

    def _track_for_cover(self):
        index = self._selected_index()
        if index < 0:
            index = self.current_index
        if index < 0 and self.tracks:
            index = 0
        if 0 <= index < len(self.tracks):
            return self.tracks[index]
        return None

    def _update_cover(self):
        track = self._track_for_cover()
        if track is None:
            self._cover_photo = None
            self.cover_label.config(image="", text="Kein Album ausgewählt")
            self.album_label.config(text="")
            return
        key = (track["artist"].lower(), track["album"].lower())
        if key not in self._cover_cache:
            if len(self._cover_cache) >= 16:
                self._cover_cache.clear()
            self._cover_cache[key] = self._make_cover_photo(taglib.read_cover(track["path"]))
        photo = self._cover_cache[key]
        if photo is not None:
            self._cover_photo = photo
            self.cover_label.config(image=photo, text="")
        else:
            self._cover_photo = None
            self.cover_label.config(image="", text="Kein Cover gefunden")
        self.album_label.config(text=f"{track['album'] or 'Unbekanntes Album'}\n"
                                     f"{track['artist'] or 'Unbekannter Interpret'}")

    def _make_cover_photo(self, data):
        if not data:
            return None
        try:
            image = Image.open(io.BytesIO(data)).convert("RGB")
            image.thumbnail((COVER_MAX, COVER_MAX))
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return tk.PhotoImage(data=buffer.getvalue())
        except Exception:
            return None

    # ---------- Kontextmenü / Bewertung / Eigenschaften ----------

    def _on_right_click(self, event):
        item = self.listbox.identify_row(event.y)
        if not item:
            return
        self.listbox.selection_set(item)
        menu = tk.Menu(self.root, tearoff=0)
        rating_menu = tk.Menu(menu, tearoff=0)
        for stars in (5, 4, 3, 2, 1, 0):
            label = stars_text(stars) if stars else "Bewertung entfernen"
            rating_menu.add_command(label=label, command=lambda s=stars: self._set_rating(s))
        menu.add_cascade(label="Sternebewertung setzen", menu=rating_menu)
        menu.add_command(label="Eigenschaften …", command=self._open_properties)
        menu.add_command(label="Abspielen", command=lambda: self.play_index(self._selected_index()))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_properties(self):
        index = self._selected_index()
        if 0 <= index < len(self.tracks):
            PropertiesDialog(self.root, self.tracks[index], on_save=self._on_track_saved)

    def _on_track_saved(self, track):
        for i, t in enumerate(self.tracks):
            if t["path"] == track["path"]:
                self.tracks[i] = track
                self.listbox.item(str(i), values=self._row_values(i))
                break
        self._update_cover()

    def _set_rating(self, stars):
        index = self._selected_index()
        if not 0 <= index < len(self.tracks):
            return
        track = self.tracks[index]
        if taglib.write_rating(track["path"], stars):
            track["rating"] = stars
            self.listbox.item(str(index), values=self._row_values(index))
        else:
            messagebox.showerror("Fehler", "Bewertung konnte nicht in die Datei geschrieben werden.")

    # ---------- Poll-Schleife ----------

    def _tick(self):
        if self.engine.finished() and self.current_index >= 0:
            self.play_next(auto=True)
        if 0 <= self.current_index < len(self.tracks):
            duration = self.tracks[self.current_index]["duration"]
            position = self.engine.position()
            if duration > 0:
                position = min(position, duration)
                if not self.seeking:
                    self.progress.set(position / duration * 1000)
            self.time_current.config(text=format_time(position))
        self.root.after(POLL_MS, self._tick)


def main():
    root = tk.Tk()
    try:
        SePlayerApp(root)
    except Exception as exc:
        messagebox.showerror("Startfehler", f"Der Player konnte nicht gestartet werden:\n{exc}")
        root.destroy()
        raise SystemExit(1)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Grafische Oberfläche des SePlayer (tkinter, läuft auf Windows, macOS und Linux).

Layout:
  links oben   -> Favoriten + Ordner-Baum (Dateisystem)
  links unten  -> Cover des ausgewählten Albums
  Mitte        -> Audiodateien des gewählten Ordners (Spalten per Rechtsklick/Drag anpassbar)
  Mitte unten  -> Player-Leiste (Play/Pause/Stop, Vor/Zurück, Fortschritt, Lautstärke)
  rechts oben  -> Logo als Overlay (verbraucht keine Nutzfläche)

Zustand (Fenstergröße, Sash-Positionen, letzter Ordner, Favoriten, Spalten, Theme,
Lautstärke) wird in state.json gespeichert und beim nächsten Start wiederhergestellt.
"""
import io
import os
import string
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pygame
from PIL import Image

from . import __version__
from . import state as statelib
from . import tags as taglib
from . import theme
from .audio import PlaybackEngine
from .convert import ConvertDialog
from .organize import AutoOrganizeDialog
from .preferences import PreferencesDialog
from .properties import PropertiesDialog
from .tray import start_tray
from .util import format_size, format_time, resource_path, stars_text

POLL_MS = 200
COVER_MAX = 240

FIELD_DEFS = [
    ("nr", "Track-Nr.", 60), ("disc", "Disc", 45), ("title", "Titel", 240),
    ("artist", "Interpret", 160), ("album", "Album", 160), ("rating", "Bewertung", 90),
    ("duration", "Dauer", 60), ("bitrate", "Bitrate", 80), ("genre", "Genre", 110),
    ("year", "Jahr", 50), ("comment", "Kommentar", 170), ("size", "Größe", 80),
    ("format", "Format", 110), ("filename", "Datei", 200), ("path", "Pfad", 260),
]
FIELD_LABELS = {fid: label for fid, label, _w in FIELD_DEFS}
DEFAULT_COLUMNS = ["nr", "title", "artist", "album", "rating", "duration", "format"]
CENTER_ANCHOR = {"nr", "disc", "duration", "year", "rating", "bitrate", "size"}

# Spalten, die per Klick direkt in der Liste editierbar sind: Spalten-id -> Tag-Feld
EDITABLE_COLUMNS = {"nr": "track", "disc": "disc", "title": "title", "artist": "artist",
                    "album": "album", "genre": "genre", "year": "year", "comment": "comment"}

SORT_KEYS = {
    "nr": lambda t: (int(t["track"]) if t["track"].isdigit() else 999, t["title"].lower()),
    "disc": lambda t: (int(t["disc"]) if t["disc"].isdigit() else 999, t["title"].lower()),
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
        theme.style_toplevel(self)
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
        root.title(f"SePlayer {__version__}")
        root.geometry(self._state.get("geometry") or "1100x680")
        root.minsize(860, 540)

        volume = int(self._state.get("volume", 70)) / 100.0
        self.engine = PlaybackEngine(volume=volume)
        self.folder = None
        self.tracks = []
        self.queue = []  # Wiedergabe-Queue (unabhängig vom angezeigten Ordner)
        self.current_index = -1
        self.loop_mode = self._state.get("loop_mode", "off")  # off | all | one
        self.seeking = False
        self._sort_column = "nr"
        self._sort_reverse = False
        self._cover_cache = {}
        self._cover_photo = None
        self._press_region = ""
        self._menus = []

        cols = self._state.get("columns")
        self.column_config = cols if cols else default_column_config()
        self.favorites = [f for f in (self._state.get("favorites") or []) if os.path.isdir(f)]

        self._build_menu()
        self._build_widgets()
        self._build_tree_roots()
        self._bind_events()
        self._refresh_favorites()
        theme.apply(self.root, self._state.get("theme", "light"))
        self._restyle_tk()
        self._load_icon()
        self.root.after(150, self._apply_layout)
        last = self._state.get("last_folder") or ""
        if self._state.get("autoload_last", True) and last and os.path.isdir(last):
            self.root.after(250, lambda: self._select_path_in_tree(last))
        self._tick()
        try:
            self.tray = start_tray(self)
        except Exception:
            self.tray = None

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    # ---------- Persistenz / Theme ----------

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
        self._state["loop_mode"] = self.loop_mode
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

    def _load_icon(self):
        """S-Logo aus dem Moniker-Logo: kleines Overlay unten rechts + Fenster-/Taskleisten-Icon."""
        try:
            name = "icon_dark.png" if theme.CURRENT == "dark" else "icon.png"
            path = resource_path(os.path.join("seplayer", "assets", name))
            if not os.path.exists(path):
                return
            img = Image.open(path).convert("RGBA")
            img.thumbnail((28, 28))
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            self._icon_photo = tk.PhotoImage(data=buffer.getvalue())
            self.icon_label.config(image=self._icon_photo)
            self.icon_label.place(in_=self.right_frame, relx=1.0, rely=1.0, anchor="se", x=-6, y=-6)
            self.root.iconphoto(True, self._icon_photo)
        except Exception:
            pass

    def _restyle_tk(self):
        for w in (self.fav_list, self.progress, self.volume):
            theme.style_tk_widget(w)
        for m in self._menus:
            theme.style_menu(m)

    # ---------- Aufbau ----------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self._menus.append(menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        self._menus.append(file_menu)
        file_menu.add_command(label="Ordner öffnen …", command=self._ask_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self._on_close)
        menubar.add_cascade(label="Datei", menu=file_menu)
        view_menu = tk.Menu(menubar, tearoff=0)
        self._menus.append(view_menu)
        view_menu.add_command(label="Spalten anpassen …", command=self._open_column_dialog)
        view_menu.add_command(label="Spalten zurücksetzen", command=self._reset_columns)
        view_menu.add_command(label="Aktuellen Ordner als Favorit pinnen", command=self._fav_add)
        view_menu.add_separator()
        view_menu.add_command(label="Einstellungen …", command=self._open_preferences)
        menubar.add_cascade(label="Ansicht", menu=view_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        self._menus.append(help_menu)
        help_menu.add_command(label="Über", command=lambda: messagebox.showinfo(
            "Über SePlayer",
            f"SePlayer {__version__}\n\nDesktop-Player für MP3, FLAC, OGG, WAV u. a.\n"
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
        theme.style_tk_widget(self.fav_list)
        fav_scroll = ttk.Scrollbar(fav_frame, orient=tk.VERTICAL, command=self.fav_list.yview)
        self.fav_list.configure(yscrollcommand=fav_scroll.set)
        self.fav_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        fav_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        fav_btns = ttk.Frame(fav_frame)
        fav_btns.pack(fill=tk.X)
        ttk.Button(fav_btns, text="+ pin", width=6, command=self._fav_add).pack(side=tk.LEFT)
        ttk.Button(fav_btns, text="– entfernen", width=10, command=self._fav_remove).pack(side=tk.LEFT, padx=2)
        self.left_pane.add(fav_frame, weight=0)

        self.tree_frame = ttk.LabelFrame(self.left_pane, text="Ordner")
        tree_frame = self.tree_frame
        self.tree = ttk.Treeview(tree_frame, show="tree")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.left_pane.add(tree_frame, weight=3)

        # Cover-Bereich fixiert (feste Höhe, nicht per Sash verschiebbar)
        cover_outer = ttk.Frame(left)
        cover_outer.pack(side=tk.BOTTOM, fill=tk.X)
        cover_outer.pack_propagate(False)
        cover_outer.configure(height=260)
        cover_frame = ttk.LabelFrame(cover_outer, text="Album-Cover")
        cover_frame.pack(fill=tk.BOTH, expand=True)
        self.cover_label = ttk.Label(cover_frame, text="Kein Album ausgewählt", anchor=tk.CENTER)
        self.cover_label.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 2))
        self.album_label = ttk.Label(cover_frame, text="", anchor=tk.CENTER,
                                     justify=tk.CENTER, wraplength=260)
        self.album_label.pack(fill=tk.X, padx=6, pady=(0, 6))

        self.right_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.right_frame, weight=4)

        list_frame = ttk.LabelFrame(self.right_frame, text="Dateien im Ordner")
        self.listbox = ttk.Treeview(list_frame, show="headings", selectmode="extended")
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))
        self._apply_columns()
        self.listbox.tag_configure("playing", foreground="#e08600")

        self.icon_label = ttk.Label(self.right_frame, text="")

        player = ttk.LabelFrame(self.right_frame, text="Wiedergabe")
        player.pack(fill=tk.X, padx=4, pady=(2, 4))

        # Lautstaerke: vertikal, oben = lauter (from_=100 oben, to_=0 unten)
        self.volume = tk.Scale(player, from_=100, to=0, orient=tk.VERTICAL, showvalue=False,
                               highlightthickness=0, bd=0, length=72, command=self._on_volume)
        self.volume.set(int(self._state.get("volume", 70)))
        self.volume.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 4))

        controls = ttk.Frame(player)
        controls.pack(fill=tk.X, padx=6, pady=4)
        ttk.Button(controls, text="⏮", width=3, command=self.play_previous).pack(side=tk.LEFT)
        self.play_button = ttk.Button(controls, text="▶", width=3, command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=2)
        ttk.Button(controls, text="⏹", width=3, command=self.stop).pack(side=tk.LEFT)
        ttk.Button(controls, text="⏭", width=3, command=self.play_next).pack(side=tk.LEFT, padx=2)
        self.loop_button = ttk.Button(controls, text=self._loop_label(), width=10, command=self._cycle_loop)
        self.loop_button.pack(side=tk.LEFT, padx=2)
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
        ttk.Label(seek_row, text="🔊").pack(side=tk.RIGHT, padx=(12, 2))

    # ---------- Spalten ----------

    def _apply_columns(self):
        visible = [c for c in self.column_config if c["visible"]]
        if not visible:
            for c in self.column_config:
                if c["id"] == "title":
                    c["visible"] = True
            visible = [c for c in self.column_config if c["visible"]]
        ids = tuple(c["id"] for c in visible)
        # displaycolumns zuerst leeren, sonst TclError wenn eine versteckte Spalte
        # noch in displaycolumns steht (das hat die Spalten "kaputt" gemacht)
        self.listbox["displaycolumns"] = ()
        self.listbox["columns"] = ids
        self.listbox["displaycolumns"] = ids
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

    def _reset_columns(self):
        self.column_config = default_column_config()
        self._apply_columns()
        self._save_state()

    def _toggle_column(self, col, visible):
        col["visible"] = visible
        self._apply_columns()
        self._save_state()

    def _open_column_menu(self, x_root, y_root):
        menu = tk.Menu(self.root, tearoff=0)
        theme.style_menu(menu)
        for col in self.column_config:
            var = tk.BooleanVar(value=col["visible"])
            menu.add_checkbutton(label=FIELD_LABELS.get(col["id"], col["id"]), variable=var,
                                 command=lambda c=col, v=var: self._toggle_column(c, v.get()))
        menu.add_separator()
        menu.add_command(label="Spalten anpassen …", command=self._open_column_dialog)
        menu.add_command(label="Spalten zurücksetzen", command=self._reset_columns)
        try:
            menu.tk_popup(x_root, y_root)
        finally:
            menu.grab_release()

    def _sync_columns_from_display(self):
        """Nach dem Verschieben per Drag: Reihenfolge aus displaycolumns übernehmen."""
        display = list(self.listbox["displaycolumns"])
        width_by_id = {c["id"]: c["width"] for c in self.column_config}
        visible_iter = iter(display)
        new_config = []
        for col in self.column_config:
            if col["visible"]:
                fid = next(visible_iter, col["id"])
                new_config.append({"id": fid, "visible": True,
                                   "width": width_by_id.get(fid, col["width"])})
            else:
                new_config.append(dict(col))
        self.column_config = new_config
        self._save_state()

    # ---------- Events ----------

    def _bind_events(self):
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Button-1>", lambda _e: self.tree.focus_set(), add="+")
        # Type-Ahead direkt auf die Widgets binden (Widget-Bindings laufen VOR den
        # Klassen-Bindings; ein Root-Binding würde von der Treeview-Klasse gebrochen)
        for w in (self.tree, self.listbox, self.fav_list):
            w.bind("<KeyPress>", self._on_tree_key, add="+")
        self.fav_list.bind("<ButtonRelease-1>", self._on_fav_select)
        self.listbox.bind("<<TreeviewSelect>>", lambda _e: self._update_cover())
        self.listbox.bind("<Double-1>", self._on_play_selected)
        self.listbox.bind("<Return>", self._on_play_selected)
        self.listbox.bind("<Control-a>", self._on_select_all)
        self.listbox.bind("<Button-3>", self._on_right_click)
        self.listbox.bind("<Button-2>", self._on_right_click)  # macOS: rechte Taste = Button-2
        self.listbox.bind("<ButtonPress-1>", self._on_list_press)
        self.listbox.bind("<Button-1>", self._on_list_click, add="+")
        self.listbox.bind("<B1-Motion>", self._on_list_motion)
        self.listbox.bind("<ButtonRelease-1>", self._on_list_release)
        self.tree.bind("<Double-1>", self._on_tree_double)
        self.progress.bind("<ButtonPress-1>", self._on_progress_press)
        self.progress.bind("<B1-Motion>", self._on_progress_motion)
        self.progress.bind("<ButtonRelease-1>", self._on_progress_release)
        self.root.bind("<space>", lambda _e: self.toggle_play())
        self.root.bind("<Right>", lambda _e: self.play_next())
        self.root.bind("<Left>", lambda _e: self.play_previous())

    def _on_list_press(self, event):
        self._press_region = self.listbox.identify_region(event.x, event.y)
        self._drag_anchor = None
        if self._press_region == "heading":
            return
        row = self.listbox.identify_row(event.y)
        if row and row.isdigit():
            self._drag_anchor = int(row)
        elif self.tracks:
            self._drag_anchor = len(self.tracks) - 1

    def _on_list_motion(self, event):
        """Mehrfachauswahl per Maus: Bereich von Anker bis aktueller Zeile markieren."""
        self._cancel_pending_edit()
        anchor = getattr(self, "_drag_anchor", None)
        if anchor is None or not self.tracks:
            return
        row = self.listbox.identify_row(event.y)
        current = int(row) if (row and row.isdigit()) else len(self.tracks) - 1
        a, b = sorted((anchor, current))
        self.listbox.selection_set(*[str(i) for i in range(a, b + 1)])

    def _on_list_release(self, event):
        if self._press_region == "heading" and self.listbox.identify_region(event.x, event.y) == "heading":
            self._sync_columns_from_display()
        self._drag_anchor = None

    def _cancel_pending_edit(self):
        if getattr(self, "_edit_after_id", None):
            try:
                self.root.after_cancel(self._edit_after_id)
            except Exception:
                pass
            self._edit_after_id = None

    def _on_list_click(self, event):
        """Klick auf eine bereits markierte Zelle.

        Spalte „Bewertung": Stern direkt per Klick setzen (Position in der Zelle = Anzahl
        Sterne, 1 Klick statt Rechtsklick-Menü). Andere Tag-Spalten: Inhalt direkt
        editieren (nach 300 ms, damit Doppelklick = Abspielen nicht kollidiert).
        """
        if self.listbox.identify_region(event.x, event.y) != "cell":
            return
        row = self.listbox.identify_row(event.y)
        col = self.listbox.identify_column(event.x)
        if not row or not col or row not in self.listbox.selection():
            return
        ids = self._visible_column_ids()
        try:
            index = int(col[1:]) - 1
        except ValueError:
            return
        if not 0 <= index < len(ids):
            return
        self._cancel_pending_edit()
        if ids[index] == "rating":
            bbox = self.listbox.bbox(row, "rating")
            if bbox:
                frac = (event.x - bbox[0]) / max(1, bbox[2])
                stars = min(5, max(1, int(frac * 5) + 1))
                self._set_rating(stars)
            return
        field = EDITABLE_COLUMNS.get(ids[index])
        if field is None:
            return
        self._edit_after_id = self.root.after(300, lambda: self._start_cell_edit(row, field))

    def _start_cell_edit(self, row, field):
        self._edit_after_id = None
        try:
            index = int(row)
            track = self.tracks[index]
        except (ValueError, IndexError):
            return
        col_id = {v: k for k, v in EDITABLE_COLUMNS.items()}.get(field)
        bbox = self.listbox.bbox(row, col_id) if col_id else None
        if not bbox:
            return
        x, y, w, h = bbox
        editor = tk.Entry(self.listbox)
        theme.style_tk_widget(editor)
        editor.place(x=x, y=y, width=w, height=h)
        editor.insert(0, str(track.get(field, "")))
        editor.select_range(0, tk.END)
        editor.focus_set()
        done = {"ok": False}

        def commit(_event=None):
            if done["ok"] or not editor.winfo_exists():
                return
            done["ok"] = True
            value = editor.get().strip()
            editor.destroy()
            if value == str(track.get(field, "")):
                return
            with self.engine.free_file(track["path"]):
                ok = taglib.write_metadata(track["path"], {field: value})
            if ok:
                track[field] = value.split("/")[0] if field in ("track", "disc") else value
                self.listbox.item(row, values=self._row_values(index))
                self._update_cover()
            else:
                messagebox.showerror(
                    "Fehler",
                    f"Tag „{field}“ konnte nicht geschrieben werden:\n{taglib.last_error or 'unbekannter Fehler'}")

        def cancel(_event=None):
            if done["ok"] or not editor.winfo_exists():
                return
            done["ok"] = True
            editor.destroy()

        editor.bind("<Return>", commit)
        editor.bind("<Escape>", cancel)
        editor.bind("<FocusOut>", commit)

    def _on_tree_double(self, _event):
        """Doppelklick im Baum: Ordner frisch von Platte neu laden."""
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        path = values[0] if values else ""
        if path and os.path.isdir(path):
            self.load_folder(path)

    # ---------- Ordner-Baum: Wurzeln ----------

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

    # ---------- Type-Ahead im Ordnerbaum (Buchstaben tippen -> springen) ----------

    def _on_tree_key(self, event):
        focus_w = self.root.focus_get()
        if isinstance(focus_w, tk.Entry):
            return
        if event.char == " ":
            return
        if event.state & 0x4 or event.state & 0x8:  # Strg/Alt nicht abfangen
            return
        if len(event.char) == 1 and event.char.isprintable():
            self._type_buf = getattr(self, "_type_buf", "") + event.char.lower()
            if getattr(self, "_type_timer", None):
                self.root.after_cancel(self._type_timer)
            self._type_timer = self.root.after(900, self._clear_type_buf)
            self.tree_frame.config(text=f"Ordner  \u201e{self._type_buf}\u201c")
            self._tree_typeahead()
            return "break"

    def _clear_type_buf(self):
        self._type_buf = ""
        self._type_timer = None
        try:
            self.tree_frame.config(text="Ordner")
        except Exception:
            pass

    def _find_typeahead(self, node, needle):
        """Ersten sichtbaren Kindknoten finden, dessen Name (case-insensitive) mit needle beginnt."""
        for child in self.tree.get_children(node):
            name = (self.tree.item(child, "text") or "").lower()
            if name.startswith(needle):
                return child
            if self.tree.item(child, "open"):
                found = self._find_typeahead(child, needle)
                if found:
                    return found
        return None

    def _tree_typeahead(self):
        needle = getattr(self, "_type_buf", "")
        if not needle:
            return
        start = self.tree.focus()
        if not start and self.tree.selection():
            start = self.tree.selection()[0]
        target = self._find_typeahead(start, needle) if start else None
        if target is None:
            for root in self.tree.get_children(""):
                if root == start:
                    continue
                name = (self.tree.item(root, "text") or "").lower()
                if name.startswith(needle):
                    target = root
                    break
                if self.tree.item(root, "open"):
                    target = self._find_typeahead(root, needle)
                    if target:
                        break
        if target is None:  # Wrap-Around: nochmal ab dem ersten Root
            for root in self.tree.get_children(""):
                name = (self.tree.item(root, "text") or "").lower()
                if name.startswith(needle):
                    target = root
                    break
                if self.tree.item(root, "open"):
                    target = self._find_typeahead(root, needle)
                    if target:
                        break
        if target:
            self.tree.selection_set(target)
            self.tree.focus(target)
            self.tree.see(target)
            if not self.tree.item(target, "open"):
                self.tree.item(target, open=True)
        if target is None:
            # Fallback: direkt im Dateisystem des aktuellen Ordners suchen
            base = getattr(self, "folder", None)
            if not base:
                selection = self.tree.selection()
                if selection:
                    values = self.tree.item(selection[0], "values")
                    base = values[0] if values else None
            if base and os.path.isdir(base):
                try:
                    for entry in sorted(os.listdir(base)):
                        full = os.path.join(base, entry)
                        if entry.lower().startswith(needle) and os.path.isdir(full):
                            self._select_path_in_tree(full)
                            return
                except OSError:
                    pass

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
            else:
                messagebox.showwarning("Favorit", f"Ordner existiert nicht mehr:\n{path}")
                del self.favorites[sel[0]]
                self._refresh_favorites()
                self._save_state()

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
        # queue/current_index bleiben bewusst stehen: Wiedergabe läuft beim Ordnerwechsel weiter
        try:
            entries = sorted(os.listdir(path))
        except OSError as exc:
            messagebox.showerror("Fehler", f"Ordner nicht lesbar:\n{path}\n\n{exc}")
            return
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isfile(full) and taglib.is_audio_file(entry):
                self.tracks.append(taglib.read_metadata(full))
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
            "disc": t["disc"],
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
        self._mark_playing()

    def _on_select_all(self, _event):
        """Strg+A: alle Titel im aktuellen Ordner markieren."""
        self.listbox.selection_set(*self.listbox.get_children())
        return "break"

    def _loop_label(self):
        return {"off": "Loop: aus", "all": "Loop: alle", "one": "Loop: einer"}[self.loop_mode]

    def _cycle_loop(self):
        order = ["off", "all", "one"]
        self.loop_mode = order[(order.index(self.loop_mode) + 1) % len(order)]
        self.loop_button.config(text=self._loop_label())
        self._save_state()

    def _mark_playing(self):
        """Markiert die Zeile des gerade spielenden Titels (orange), auch nach Ordnerwechsel."""
        playing_path = None
        if 0 <= self.current_index < len(self.queue) and (self.engine.is_playing() or self.engine.paused):
            playing_path = self.queue[self.current_index]["path"]
        for i in range(len(self.tracks)):
            tags = [t for t in self.listbox.item(str(i), "tags") if t != "playing"]
            if playing_path and self.tracks[i]["path"] == playing_path:
                tags.append("playing")
            self.listbox.item(str(i), tags=tuple(tags))

    def _selected_indices(self):
        result = []
        for item in self.listbox.selection():
            try:
                result.append(int(item))
            except ValueError:
                pass
        return sorted(result)

    # ---------- Wiedergabe ----------

    def _on_play_selected(self, _event):
        self._cancel_pending_edit()
        indices = self._selected_indices()
        if indices:
            self.play_index(indices[0])

    def play_index(self, index):
        """Spielt Titel `index` der aktuell angezeigten Liste (setzt die Queue auf diese Liste)."""
        self.queue = list(self.tracks)
        self._play_queue_index(index)

    def _play_queue_index(self, index):
        if not 0 <= index < len(self.queue):
            return
        if not self.engine.available:
            messagebox.showwarning(
                "Kein Audio-Gerät",
                "Die Audiowiedergabe ist nicht verfügbar — der Audio-Mixer konnte nicht initialisiert werden.")
            return
        track = self.queue[index]
        try:
            self.engine.load(track["path"])
            self.engine.play()
        except pygame.error as exc:
            messagebox.showwarning(
                "Wiedergabe nicht möglich",
                f"{track['filename']}\n\nDieses Format wird nicht unterstützt.\n({exc})")
            return
        self.current_index = index
        for i, t in enumerate(self.tracks):
            if t["path"] == track["path"]:
                if len(self._selected_indices()) <= 1:
                    self.listbox.selection_set(str(i))
                self.listbox.see(str(i))
                self.listbox.focus(str(i))
                break
        self.play_button.config(text="⏸")
        self._mark_playing()
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
            indices = self._selected_indices()
            index = indices[0] if indices else self.current_index
            if index < 0:
                index = 0
            self.play_index(index)

    def stop(self):
        self.engine.stop()
        self.play_button.config(text="▶")
        self.progress.set(0)
        self.time_current.config(text="00:00")
        self._mark_playing()

    def play_next(self, auto=False):
        if not self.queue:
            return
        nxt = self.current_index + 1
        if nxt >= len(self.queue):
            if auto:
                if self.loop_mode == "one":
                    self._play_queue_index(self.current_index)
                    return
                if self.loop_mode == "all":
                    nxt = 0
                else:
                    self.stop()
                    return
            else:
                nxt = 0
        self._play_queue_index(nxt)

    def play_previous(self):
        if not self.queue:
            return
        if self.engine.position() > 3:
            self.engine.seek(0)
            return
        prev = self.current_index - 1
        if prev < 0:
            prev = len(self.queue) - 1
        self._play_queue_index(prev)

    def _progress_fraction(self, event):
        width = max(1, self.progress.winfo_width())
        return min(1.0, max(0.0, event.x / width))

    def _seek_to(self, fraction):
        if 0 <= self.current_index < len(self.queue) and self.engine.current_path:
            duration = self.queue[self.current_index]["duration"]
            if duration > 0:
                try:
                    self.engine.seek(fraction * duration)
                    self.play_button.config(text="⏸")
                except pygame.error:
                    pass

    def _on_progress_press(self, event):
        """Klick in den Fortschrittsbalken: sofort an diese Stelle springen."""
        self.seeking = True
        fraction = self._progress_fraction(event)
        self.progress.set(fraction * 1000)
        self._seek_to(fraction)
        return "break"

    def _on_progress_motion(self, event):
        if self.seeking:
            self.progress.set(self._progress_fraction(event) * 1000)
        return "break"

    def _on_progress_release(self, event):
        fraction = self._progress_fraction(event)
        self.progress.set(fraction * 1000)
        self._seek_to(fraction)
        self.seeking = False
        return "break"

    def _on_volume(self, value):
        self.engine.set_volume(float(value) / 100.0)

    # ---------- Cover ----------

    def _track_for_cover(self):
        if 0 <= self.current_index < len(self.queue) and self.engine.current_path:
            return self.queue[self.current_index]
        indices = self._selected_indices()
        index = indices[0] if indices else -1
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

    # ---------- Kontextmenüs / Bewertung / Eigenschaften / Preferences ----------

    def _on_right_click(self, event):
        if self.listbox.identify_region(event.x, event.y) == "heading":
            self._open_column_menu(event.x_root, event.y_root)
            return
        item = self.listbox.identify_row(event.y)
        if not item:
            return
        if item not in self.listbox.selection():
            self.listbox.selection_set(item)
        indices = self._selected_indices()
        menu = tk.Menu(self.root, tearoff=0)
        theme.style_menu(menu)
        rating_menu = tk.Menu(menu, tearoff=0)
        theme.style_menu(rating_menu)
        for stars in (5, 4, 3, 2, 1, 0):
            label = stars_text(stars) if stars else "Bewertung entfernen"
            rating_menu.add_command(label=label, command=lambda s=stars: self._set_rating(s))
        menu.add_cascade(label=f"Sternebewertung setzen ({len(indices)} Datei(en))", menu=rating_menu)
        menu.add_command(label=f"Eigenschaften … ({len(indices)} Datei(en))", command=self._open_properties)
        menu.add_command(label=f"Auto-Organize: umbenennen … ({len(indices)} Datei(en))",
                         command=self._open_auto_organize)
        menu.add_command(label=f"Konvertieren nach … ({len(indices)} Datei(en))",
                         command=self._open_convert)
        menu.add_command(label="Im Explorer/Finder öffnen", command=self._show_in_file_manager)
        menu.add_command(label="Abspielen", command=self._on_play_selected)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_convert(self):
        indices = self._selected_indices()
        tracks = [self.tracks[i] for i in indices if 0 <= i < len(self.tracks)]
        if tracks:
            ConvertDialog(self.root, tracks, on_done=self._on_converted,
                          guard=self.engine.free_file)

    def _on_converted(self):
        if self.folder and os.path.isdir(self.folder):
            self.load_folder(self.folder)
        else:
            self._fill_list()

    def _open_auto_organize(self):
        indices = self._selected_indices()
        tracks = [self.tracks[i] for i in indices if 0 <= i < len(self.tracks)]
        if tracks:
            AutoOrganizeDialog(self.root, tracks, on_done=self._on_organized,
                               guard=self.engine.free_file)

    def _on_organized(self):
        """Nach Auto-Organize: Ordner komplett frisch von Platte neu laden."""
        if self.folder and os.path.isdir(self.folder):
            self.load_folder(self.folder)
        else:
            self._fill_list()
            self._update_cover()

    def _show_in_file_manager(self):
        """Öffnet den Dateimanager an der Stelle der ausgewählten Datei."""
        indices = self._selected_indices()
        if not indices:
            return
        path = self.tracks[indices[0]]["path"]
        import subprocess
        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer", "/select,", os.path.abspath(path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(os.path.abspath(path)) or "/"])
        except Exception as exc:
            messagebox.showerror("Fehler", f"Dateimanager konnte nicht geöffnet werden:\n{exc}")

    def _open_properties(self):
        indices = self._selected_indices()
        if indices:
            tracks = [self.tracks[i] for i in indices if 0 <= i < len(self.tracks)]
            if tracks:
                PropertiesDialog(self.root, tracks, on_save=self._on_track_saved,
                                 guard=self.engine.free_file)

    def _on_track_saved(self, track):
        for i, t in enumerate(self.tracks):
            if t["path"] == track["path"]:
                self.tracks[i] = track
                self.listbox.item(str(i), values=self._row_values(i))
                break
        self._update_cover()

    def _set_rating(self, stars):
        indices = self._selected_indices()
        if not indices:
            return
        failed = []
        for index in indices:
            track = self.tracks[index]
            with self.engine.free_file(track["path"]):
                ok = taglib.write_rating(track["path"], stars)
            if ok:
                track["rating"] = stars
                self.listbox.item(str(index), values=self._row_values(index))
            else:
                failed.append(track["filename"])
        if failed:
            messagebox.showerror("Fehler", "Bewertung konnte nicht geschrieben werden bei:\n"
                                           + "\n".join(failed[:10]))

    def _open_preferences(self):
        PreferencesDialog(self.root, self._state, self._on_prefs_saved)

    def _on_prefs_saved(self, prefs):
        self._state.update(prefs)
        theme.apply(self.root, prefs.get("theme", "light"))
        self._restyle_tk()
        self._load_icon()
        volume = int(prefs.get("volume", 70))
        self.volume.set(volume)
        self.engine.set_volume(volume / 100.0)
        self._save_state()

    # ---------- Poll-Schleife ----------

    def _tick(self):
        if self.engine.finished() and self.current_index >= 0:
            self.play_next(auto=True)
        self._mark_playing()
        if 0 <= self.current_index < len(self.queue):
            duration = self.queue[self.current_index]["duration"]
            position = self.engine.position()
            if duration > 0:
                position = min(position, duration)
                if not self.seeking:
                    self.progress.set(position / duration * 1000)
            self.time_current.config(text=format_time(position))
        self.root.after(POLL_MS, self._tick)


def main():
    root = tk.Tk()

    def _on_callback_error(exc, val, tb):
        import traceback
        messagebox.showerror("Interner Fehler", "".join(traceback.format_exception(exc, val, tb)))

    root.report_callback_exception = _on_callback_error
    try:
        SePlayerApp(root)
    except Exception as exc:
        messagebox.showerror("Startfehler", f"Der Player konnte nicht gestartet werden:\n{exc}")
        root.destroy()
        raise SystemExit(1)
    root.mainloop()


if __name__ == "__main__":
    main()

"""Grafische Oberfläche des MP3-Players (tkinter, läuft auf Windows, macOS und Linux).

Layout:
  links oben   -> Ordner-Baum (Dateisystem)
  links unten  -> Cover des ausgewählten Albums
  Mitte        -> Audiodateien des gewählten Ordners (mit Tags/Sternebewertung)
  Mitte unten  -> Player-Leiste (Play/Pause/Stop, Vor/Zurück, Fortschritt, Lautstärke)
"""
import io
import os
import string
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pygame
from PIL import Image

from . import tags as taglib
from .audio import PlaybackEngine

POLL_MS = 200
COVER_MAX = 240

COLUMNS = ("nr", "title", "artist", "album", "rating", "duration", "info")
HEADINGS = {
    "nr": "Nr.", "title": "Titel", "artist": "Interpret", "album": "Album",
    "rating": "Bewertung", "duration": "Dauer", "info": "Format",
}
COLUMN_WIDTHS = {
    "nr": 40, "title": 240, "artist": 170, "album": 170,
    "rating": 100, "duration": 60, "info": 110,
}
SORT_KEYS = {
    "nr": lambda t: (int(t["track"]) if t["track"].isdigit() else 999, t["title"].lower()),
    "title": lambda t: t["title"].lower(),
    "artist": lambda t: t["artist"].lower(),
    "album": lambda t: t["album"].lower(),
    "rating": lambda t: t["rating"],
    "duration": lambda t: t["duration"],
    "info": lambda t: t["path"].lower(),
}


def format_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def stars_text(n):
    n = max(0, min(5, int(n)))
    return "★" * n + "☆" * (5 - n) if n else "–"


class Mp3PlayerApp:
    def __init__(self, root):
        self.root = root
        root.title("MP3 Player")
        root.geometry("1024x640")
        root.minsize(780, 500)

        self.engine = PlaybackEngine(volume=0.7)
        self.folder = None
        self.tracks = []
        self.current_index = -1
        self.seeking = False
        self._sort_column = "nr"
        self._sort_reverse = False
        self._cover_cache = {}
        self._cover_photo = None

        self._build_menu()
        self._build_widgets()
        self._build_tree_roots()
        self._bind_events()
        self._tick()

    # ---------- Aufbau ----------

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Ordner öffnen …", command=self._ask_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Beenden", command=self.root.destroy)
        menubar.add_cascade(label="Datei", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Über", command=lambda: messagebox.showinfo(
            "Über MP3 Player",
            "MP3 Player\n\nDesktop-Player für MP3, FLAC, OGG, WAV u. a.\n"
            "Ordner-Navigation, Tags & Sternebewertungen (POPM/RATING), Album-Cover."))
        menubar.add_cascade(label="Hilfe", menu=help_menu)
        self.root.config(menu=menubar)

    def _build_widgets(self):
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main_pane)
        main_pane.add(left, weight=1)
        left_pane = ttk.PanedWindow(left, orient=tk.VERTICAL)
        left_pane.pack(fill=tk.BOTH, expand=True)

        tree_frame = ttk.LabelFrame(left_pane, text="Ordner")
        self.tree = ttk.Treeview(tree_frame, show="tree")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        left_pane.add(tree_frame, weight=3)

        cover_frame = ttk.LabelFrame(left_pane, text="Album-Cover")
        self.cover_label = ttk.Label(cover_frame, text="Kein Album ausgewählt", anchor=tk.CENTER)
        self.cover_label.pack(fill=tk.BOTH, expand=True, padx=6, pady=(6, 2))
        self.album_label = ttk.Label(cover_frame, text="", anchor=tk.CENTER,
                                     justify=tk.CENTER, wraplength=230)
        self.album_label.pack(fill=tk.X, padx=6, pady=(0, 6))
        left_pane.add(cover_frame, weight=2)

        right = ttk.Frame(main_pane)
        main_pane.add(right, weight=4)

        list_frame = ttk.LabelFrame(right, text="Dateien im Ordner")
        self.listbox = ttk.Treeview(list_frame, columns=COLUMNS, show="headings", selectmode="browse")
        for col in COLUMNS:
            self.listbox.heading(col, text=HEADINGS[col], command=lambda c=col: self._sort_by(c))
            anchor = tk.CENTER if col in ("nr", "duration") else tk.W
            self.listbox.column(col, width=COLUMN_WIDTHS[col], stretch=True, anchor=anchor)
        list_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=list_scroll.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 2))

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
        self.listbox.bind("<<TreeviewSelect>>", lambda _e: self._update_cover())
        self.listbox.bind("<Double-1>", self._on_double_click)
        self.listbox.bind("<Button-3>", self._on_right_click)
        self.listbox.bind("<Button-2>", self._on_right_click)  # macOS: rechte Taste = Button-2
        self.progress.bind("<ButtonPress-1>", lambda _e: setattr(self, "seeking", True))
        self.progress.bind("<ButtonRelease-1>", self._on_seek_release)
        self.root.bind("<space>", lambda _e: self.toggle_play())
        self.root.bind("<Right>", lambda _e: self.play_next())
        self.root.bind("<Left>", lambda _e: self.play_previous())

    # ---------- Ordner-Baum ----------

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
            try:
                entries = sorted(os.listdir(path))
            except OSError:
                self.tree.insert(node, "end", text="(kein Zugriff)", values=("",))
                return
            for entry in entries:
                full = os.path.join(path, entry)
                if os.path.isdir(full) and not (os.name != "nt" and entry.startswith(".")):
                    self._insert_dir(node, full)

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
                meta["path"] = full
                self.tracks.append(meta)
        self._sort_reverse = False
        self._sort_tracks()
        self._fill_list()
        self._update_cover()

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

    def _fill_list(self):
        self.listbox.delete(*self.listbox.get_children())
        for i in range(len(self.tracks)):
            self.listbox.insert("", "end", iid=str(i), values=self._row_values(i))

    def _row_values(self, index):
        track = self.tracks[index]
        ext = os.path.splitext(track["path"])[1].lstrip(".").upper()
        info = ext + (f" · {track['bitrate']} kbps" if track["bitrate"] else "")
        return (track["track"] or str(index + 1), track["title"], track["artist"],
                track["album"], format_time(track["duration"]), stars_text(track["rating"]), info)

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
        track = self.tracks[index]
        try:
            self.engine.load(track["path"])
            self.engine.play()
        except pygame.error as exc:
            messagebox.showwarning(
                "Wiedergabe nicht möglich",
                f"{os.path.basename(track['path'])}\n\nDieses Format wird nicht unterstützt.\n({exc})")
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

    # ---------- Kontextmenü / Bewertung ----------

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
        menu.add_command(label="Abspielen", command=lambda: self.play_index(self._selected_index()))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

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
        Mp3PlayerApp(root)
    except Exception as exc:
        messagebox.showerror("Startfehler", f"Der Player konnte nicht gestartet werden:\n{exc}")
        root.destroy()
        raise SystemExit(1)
    root.mainloop()


if __name__ == "__main__":
    main()

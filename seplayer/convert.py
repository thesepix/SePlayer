"""Audiodateien konvertieren (z. B. WAV -> FLAC/MP3) über ffmpeg.

ffmpeg kommt gebündelt mit (imageio-ffmpeg, im PyInstaller-Build als Binary enthalten);
Fallback: ffmpeg im PATH.
"""
import glob
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from . import theme


def find_ffmpeg():
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        for path in glob.glob(os.path.join(sys._MEIPASS, "ffmpeg*")):
            if os.path.isfile(path):
                return path
    return shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")


def convert_file(src, dst, fmt, ffmpeg):
    if fmt == "flac":
        args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-c:a", "flac", dst]
    else:
        args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                "-c:a", "libmp3lame", "-b:a", "320k", dst]
    try:
        return subprocess.run(args, capture_output=True).returncode == 0
    except OSError:
        return False


class ConvertDialog(tk.Toplevel):
    def __init__(self, master, tracks, on_done=None, guard=None):
        super().__init__(master)
        theme.style_toplevel(self)
        self.tracks = tracks
        self.on_done = on_done
        self.guard = guard
        self.title(f"Konvertieren — {len(tracks)} Datei(en)")
        self.geometry("640x420")
        self.transient(master)

        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Zielformat:").pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value="flac")
        ttk.Radiobutton(top, text="FLAC (verlustfrei)", value="flac",
                        variable=self.fmt_var, command=self._refresh).pack(side=tk.LEFT, padx=6)
        ttk.Radiobutton(top, text="MP3 (320 kbps)", value="mp3",
                        variable=self.fmt_var, command=self._refresh).pack(side=tk.LEFT, padx=6)

        self.preview = tk.Listbox(self, font=("TkDefaultFont", 9))
        theme.style_tk_widget(self.preview)
        self.preview.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(buttons, text="Konvertieren", command=self._convert).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 6))
        self._refresh()
        self.grab_set()

    def _target(self, track):
        ext = ".flac" if self.fmt_var.get() == "flac" else ".mp3"
        return os.path.join(os.path.dirname(track["path"]),
                            os.path.splitext(track["filename"])[0] + ext)

    def _refresh(self):
        self.preview.delete(0, tk.END)
        for track in self.tracks:
            self.preview.insert(tk.END, f"{track['filename']}  ->  {os.path.basename(self._target(track))}")

    def _convert(self):
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            messagebox.showerror(
                "Konvertieren",
                "ffmpeg wurde nicht gefunden. Bitte imageio-ffmpeg installieren oder ffmpeg ins PATH legen.",
                parent=self)
            return
        fmt = self.fmt_var.get()
        converted, skipped, errors = [], [], []
        for track in self.tracks:
            dst = self._target(track)
            if os.path.exists(dst):
                skipped.append(os.path.basename(dst))
                continue
            if self.guard is not None:
                with self.guard(track["path"]):
                    ok = convert_file(track["path"], dst, fmt, ffmpeg)
            else:
                ok = convert_file(track["path"], dst, fmt, ffmpeg)
            if ok:
                converted.append(os.path.basename(dst))
            else:
                errors.append(track["filename"])
                if os.path.exists(dst):
                    try:
                        os.remove(dst)
                    except OSError:
                        pass
        if self.on_done:
            self.on_done()
        msg = f"{len(converted)} Datei(en) konvertiert ({fmt.upper()})."
        if skipped:
            msg += f"\n{len(skipped)} übersprungen (existiert bereits)."
        if errors:
            msg += "\n\nFehler bei:\n" + "\n".join(errors[:10])
        if errors:
            messagebox.showerror("Konvertieren", msg, parent=self)
        else:
            messagebox.showinfo("Konvertieren", msg, parent=self)
        self.destroy()

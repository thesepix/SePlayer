"""Kleine Formatierungs-Helfer + Dateinamen-Muster (Auto-Organize)."""
import re

PATTERN_FIELDS = ["title", "artist", "album", "albumartist", "composer",
                  "genre", "year", "track", "disc", "comment"]


def apply_filename_pattern(pattern, meta, fallback_index=1):
    """Wendet ein Umbenennungs-Muster auf die Tags an.

    Muster-Syntax: `##` = Tracknummer zweistellig, `#` = Tracknummer,
    `<feld>` = Feld per spitzen Klammern (MediaMonkey-Stil), außerdem werden
    Feldnamen als ganze Wörter ersetzt (z. B. `## - artist - title`).
    Ungültige Dateizeichen (\\/:*?"<>|) werden durch "-" ersetzt.
    """
    track = str(meta.get("track") or fallback_index)
    result = pattern.replace("##", track.zfill(2))
    result = result.replace("#", track)

    def angle(match):
        key = match.group(1).strip().lower()
        value = meta.get(key, "")
        return str(value) if value else match.group(0)

    result = re.sub(r"<([^<>]+)>", angle, result)
    for key in PATTERN_FIELDS:
        value = meta.get(key, "")
        if value:
            result = re.sub(r"\b" + re.escape(key) + r"\b", str(value), result,
                            flags=re.IGNORECASE)
    result = re.sub(r'[\\/:*?"<>|]', "-", result)
    result = re.sub(r"\s+", " ", result).strip(" .")
    return result


def format_time(seconds):
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def format_size(nbytes):
    nbytes = max(0, int(nbytes))
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024 or unit == "GB":
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024
    return f"{nbytes:.1f} GB"


def stars_text(n):
    n = max(0, min(5, int(n)))
    return "★" * n + "☆" * (5 - n) if n else "–"


import os
import sys


def resource_path(rel):
    """Pfad zu gebündelten Assets (PyInstaller _MEIPASS bzw. Projekt-Root im Dev)."""
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), rel)

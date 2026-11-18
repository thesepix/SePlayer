"""Kleine Formatierungs-Helfer."""


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

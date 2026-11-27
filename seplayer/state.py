"""Persistenter Zustand (Fenster, Sash-Positionen, letzter Ordner, Favoriten, Spalten, Theme).

Liegt als JSON im plattformüblichen Config-Verzeichnis:
  Windows: %APPDATA%/SePlayer/state.json
  macOS:   ~/Library/Application Support/SePlayer/state.json
  Linux:   $XDG_CONFIG_HOME/SePlayer/state.json (oder ~/.config/SePlayer/state.json)
"""
import json
import os
import sys

STATE_FILE = "state.json"

DEFAULT_STATE = {
    "geometry": "1100x680",
    "sash_main": 300,
    "sash_left": 400,
    "last_folder": "",
    "favorites": [],
    "columns": [],
    "theme": "light",
    "autoload_last": True,
    "volume": 70,
    "loop_mode": "off",
}


def config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    path = os.path.join(base, "SePlayer")
    os.makedirs(path, exist_ok=True)
    return path


def state_path():
    return os.path.join(config_dir(), STATE_FILE)


def load_state():
    state = dict(DEFAULT_STATE)
    try:
        with open(state_path(), "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            state.update(stored)
    except (OSError, ValueError):
        pass
    return state


def save_state(state):
    try:
        with open(state_path(), "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False

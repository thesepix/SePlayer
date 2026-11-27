"""System-Tray-Icon (rechts unten in Windows) über pystray.

Klick auf das Icon toggelt Play/Pause — ohne das Fenster in den Vordergrund zu holen.
Menü: Play/Pause, Zurück, Weiter, Stop, Fenster zeigen, Beenden.
pystray läuft in einem eigenen Thread; alle Tk-Aktionen werden über root.after(0, …)
in den Tk-Hauptthread verlagert.
"""
import os
import threading

from .util import resource_path


def start_tray(app):
    """Startet das Tray-Icon für die App. Rückgabe: pystray.Icon oder None (kein Tray verfügbar)."""
    try:
        import pystray
        from PIL import Image
    except Exception:
        return None
    try:
        image = Image.open(resource_path(os.path.join("seplayer", "assets", "icon.png"))).convert("RGBA")
        image = image.resize((64, 64), Image.LANCZOS)
    except Exception:
        image = Image.new("RGBA", (64, 64), (20, 20, 20, 255))

    def run(fn):
        return lambda *args: app.root.after(0, fn)

    menu = pystray.Menu(
        pystray.MenuItem("Play / Pause", run(app.toggle_play), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("⏮ Zurück", run(app.play_previous)),
        pystray.MenuItem("⏭ Weiter", run(app.play_next)),
        pystray.MenuItem("⏹ Stop", run(app.stop)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Fenster zeigen", run(app._show_window)),
        pystray.MenuItem("Beenden", run(app._on_close)),
    )
    icon = pystray.Icon("SePlayer", image, "SePlayer", menu)

    def _run():
        try:
            icon.run()
        except Exception:
            pass

    threading.Thread(target=_run, daemon=True).start()
    return icon

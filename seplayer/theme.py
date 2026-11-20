"""Farbschema (Hell/Dunkel) für die GUI. Wird in state.json persistiert."""
import sys
import tkinter as tk
from tkinter import ttk

PALETTES = {
    "light": dict(
        bg="#f0f0f0", fg="#1a1a1a", field_bg="#ffffff", trough="#dcdcdc",
        select_bg="#3874f2", select_fg="#ffffff", heading_bg="#e2e2e2", heading_fg="#1a1a1a",
        insert="#1a1a1a", disabled="#909090", border="#c0c0c0",
    ),
    "dark": dict(
        bg="#2b2b2b", fg="#e8e8e8", field_bg="#3c3c3c", trough="#1e1e1e",
        select_bg="#3a6ea5", select_fg="#ffffff", heading_bg="#424242", heading_fg="#e8e8e8",
        insert="#e8e8e8", disabled="#777777", border="#555555",
    ),
}

CURRENT = "light"


def palette():
    return PALETTES[CURRENT]


def _dark_titlebar_windows(root):
    """Windows 10/11: Titelleiste im Dark Mode dunkel färben (DWM)."""
    if sys.platform != "win32" or CURRENT != "dark":
        return
    try:
        import ctypes
        hwnd = int(root.wm_frame(), 16)
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(value),
                                                    ctypes.sizeof(value))
    except Exception:
        pass


def apply(root, name="light"):
    """Setzt das Farbschema für root und alle ttk-Widgets (Toplevels teilen den Style)."""
    global CURRENT
    CURRENT = name if name in PALETTES else "light"
    p = PALETTES[CURRENT]
    root.configure(bg=p["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=p["bg"], foreground=p["fg"],
                    fieldbackground=p["field_bg"], troughcolor=p["trough"],
                    bordercolor=p["border"], insertcolor=p["insert"])
    for widget in ("TFrame", "TPanedwindow", "TSeparator"):
        style.configure(widget, background=p["bg"])
    style.configure("TLabel", background=p["bg"], foreground=p["fg"])
    style.configure("TLabelframe", background=p["bg"], bordercolor=p["border"])
    style.configure("TLabelframe.Label", background=p["bg"], foreground=p["fg"])
    style.configure("TButton", background=p["heading_bg"], foreground=p["fg"], bordercolor=p["border"])
    style.map("TButton", background=[("active", p["trough"])],
              foreground=[("disabled", p["disabled"])])
    style.configure("TEntry", fieldbackground=p["field_bg"], foreground=p["fg"])
    style.configure("TNotebook", background=p["bg"], bordercolor=p["border"])
    style.configure("TNotebook.Tab", background=p["heading_bg"], foreground=p["fg"])
    style.map("TNotebook.Tab", background=[("selected", p["bg"])])
    style.configure("Treeview", background=p["field_bg"], fieldbackground=p["field_bg"],
                    foreground=p["fg"], bordercolor=p["border"])
    style.map("Treeview", background=[("selected", p["select_bg"])],
              foreground=[("selected", p["select_fg"])])
    style.configure("Treeview.Heading", background=p["heading_bg"], foreground=p["heading_fg"])
    style.map("Treeview.Heading", background=[("active", p["trough"])])
    for widget in ("TCheckbutton", "TRadiobutton"):
        style.configure(widget, background=p["bg"], foreground=p["fg"])
    style.configure("TSpinbox", fieldbackground=p["field_bg"], foreground=p["fg"])
    style.configure("TCombobox", fieldbackground=p["field_bg"], foreground=p["fg"])
    style.configure("TScale", background=p["bg"], troughcolor=p["trough"])
    for orient in ("Vertical", "Horizontal"):
        style.configure(f"{orient}.TScrollbar", background=p["heading_bg"],
                        troughcolor=p["trough"], arrowcolor=p["fg"], bordercolor=p["border"])
        style.map(f"{orient}.TScrollbar", background=[("active", p["select_bg"])])
    _dark_titlebar_windows(root)


def style_tk_widget(w):
    """Färbt ein klassisches tk-Widget (Listbox, Scale, Entry …) passend ein."""
    p = palette()
    try:
        w.configure(bg=p["bg"], fg=p["fg"], selectbackground=p["select_bg"],
                    selectforeground=p["select_fg"], highlightbackground=p["bg"],
                    troughcolor=p["trough"], insertbackground=p["insert"])
    except tk.TclError:
        pass


def style_menu(m):
    p = palette()
    try:
        m.configure(bg=p["field_bg"], fg=p["fg"], activebackground=p["select_bg"],
                    activeforeground=p["select_fg"])
    except tk.TclError:
        pass


def style_toplevel(top):
    """Hintergrund eines Dialog-Fensters (Toplevel) passend einfärben."""
    try:
        top.configure(bg=palette()["bg"])
    except tk.TclError:
        pass

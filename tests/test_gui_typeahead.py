"""GUI-Test Type-Ahead im Ordnerbaum — laeuft nur mit DISPLAY + tkinter (sonst skip).
Headless z. B. per Xvfb, Rezept in tests/README.md."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


def _tk_available():
    if not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter  # noqa: F401
        return True
    except Exception:
        return False


@unittest.skipUnless(_tk_available(), "braucht DISPLAY + tkinter (Xvfb siehe tests/README.md)")
class TestTreeTypeahead(unittest.TestCase):
    def test_typeahead_jumps_to_sibling(self):
        import tkinter as tk
        from seplayer.gui import SePlayerApp

        base = tempfile.mkdtemp(prefix="seplayer_test_")
        for n in ["Alpha", "Funckarma - Solid State", "RJELEVEN - Remixes"]:
            os.makedirs(os.path.join(base, n))
        root = tk.Tk()
        done = {}
        try:
            app = SePlayerApp(root)
            root.update()

            def step():
                try:
                    app._select_path_in_tree(base)
                    root.update()
                    kids = {app.tree.item(c, "text"): c
                            for c in app.tree.get_children(app.tree.selection()[0])}
                    fk = [c for t, c in kids.items() if t.lower().startswith("funckarma")][0]
                    app.tree.see(fk)
                    root.update()
                    bbox = app.tree.bbox(fk)
                    app.tree.event_generate("<Button-1>", x=bbox[0] + 5, y=bbox[1] + bbox[3] // 2)
                    root.update()
                    app.tree.event_generate("<KeyPress>", keysym="r")
                    root.update()
                    done["sel"] = [app.tree.item(s, "text") for s in app.tree.selection()]
                finally:
                    root.destroy()

            root.after(700, step)
            root.mainloop()
        finally:
            shutil.rmtree(base, ignore_errors=True)
        sel = done.get("sel") or []
        self.assertTrue(sel and sel[0].lower().startswith("rjeleven"),
                        f"erwartet RJELEVEN, bekommen: {sel}")


if __name__ == "__main__":
    unittest.main()

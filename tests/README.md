# Tests

Vor jedem Commit reicht: **`python3 tools/check.py`** (Syntax + AST + Workflow-YAML + alle Unit-Tests).

## Unit-Tests (ohne Display)

- `test_util.py` — Dateinamen-Parsing (`title_from_filename`, `apply_filename_pattern`)
- `test_tags.py` — Tag/Rating-Roundtrip auf temporaerer WAV-Datei (mutagen)

## GUI-Test (headless mit Xvfb)

`test_gui_typeahead.py` laeuft nur, wenn `DISPLAY` gesetzt und tkinter importierbar ist (sonst `skip`).

Rezept (Debian/Ubuntu-Sandbox ohne root, Pakete nach /tmp entpacken):

```bash
apt-get -o Dir::State::Lists=/tmp/apt/lists -o Dir::Cache=/tmp/apt/cache \
        -o Dir::State::status=/tmp/apt/state/status -o APT::Get::AllowUnauthenticated=true update
apt-get <gleiche -o-Optionen> install --download-only -y xvfb libtk8.6 libtcl8.6 fontconfig-config fonts-dejavu-core
mkdir -p /tmp/xroot && for d in /tmp/apt/cache/archives/*.deb; do dpkg -x "$d" /tmp/xroot; done
# Xvfb-Binary patchen: b'/usr/bin\0' -> b'/tmp/x\0\0\0' und xkbcomp nach /tmp/x/xkbcomp
mkdir -p /tmp/x && cp /tmp/xroot/usr/bin/xkbcomp /tmp/x/xkbcomp
python3 -c "d=open('/tmp/xroot/usr/bin/Xvfb','rb').read(); \
  open('/tmp/Xvfb','wb').write(d.replace(b'/usr/bin\x00', b'/tmp/x\x00\x00\x00')); import os; os.chmod('/tmp/Xvfb',0o755)"
LD_LIBRARY_PATH=/tmp/xroot/usr/lib/x86_64-linux-gnu /tmp/Xvfb :99 -screen 0 1280x800x24 -ac \
  -xkbdir /tmp/xroot/usr/share/X11/xkb &
mkdir -p /tmp/fccache && printf '<?xml version="1.0"?>\n<fontconfig><dir>/tmp/xroot/usr/share/fonts</dir><cachedir>/tmp/fccache</cachedir></fontconfig>\n' > /tmp/fonts.conf
DISPLAY=:99 LD_LIBRARY_PATH=/tmp/xroot/usr/lib/x86_64-linux-gnu \
  TCL_LIBRARY=/tmp/xroot/usr/share/tcltk/tcl8.6 TK_LIBRARY=/tmp/xroot/usr/share/tcltk/tk8.6 \
  FONTCONFIG_FILE=/tmp/fonts.conf python3 tools/check.py
```

Events werden per `widget.event_generate("<KeyPress>", keysym="r")` simuliert.

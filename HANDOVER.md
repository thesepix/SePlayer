# SePlayer — Handover / Kontext für die nächste KI

**Repo:** `thesepix/SePlayer` (privat) · **Aktueller Stand:** `v1.3.33` (Tag + Release vorhanden, CI grün)
**Projekt:** privater Desktop-Musikplayer (MediaMonkey-artig) für Windows/macOS/Linux.
**Nutzer:** deutschsprachig, testet primär auf einem Windows-PC, auch Mac. Mag robuste Datei-Sperr-Behandlung
(Umbenennen/Beschreiben während der Wiedergabe), versionierte Binaries (nie „welche Version teste ich gerade?"),ällt nicht gern auf CI-Benachrichtigungs-Mails und stale Exes herein.

---

## 1. Stack & Build

- Python 3.12, tkinter/ttk GUI, pygame (mixer) Audio, mutagen (Tags), Pillow (Cover/Icon), pystray (Tray), imageio-ffmpeg (Konvertierung).
- PyInstaller **onefile, windowed**: `se_player.spec` (datas: `seplayer/assets/icon.png` + `icon_dark.png`; binaries: ffmpeg aus imageio-ffmpeg; icon: `icon.ico`; hiddenimports u. a. pystray._win32).
- CI `.github/workflows/build.yml`: `on: push branches:[main], tags:["v*"], workflow_dispatch`; Matrix windows-latest / macos-latest / ubuntu-22.04; `permissions: contents: write`.
  - Artefakt-Upload nur bei main-Pushes (`retention-days: 3`, `continue-on-error: true`).
  - Release bei Tags `v*` via softprops/action-gh-release mit versionierten Dateinamen (`SePlayer-vX.Y.Z.exe/.dmg`, `SePlayer-linux-vX.Y.Z`; auf main: `dev-<sha>`).
  - Cleanup-Step löscht alle älteren Releases (nur neuestes bleibt) — `shell: bash`, `continue-on-error: true`, `gh api .../releases?per_page=100 --jq ... .id` + DELETE (NICHT `gh release list --json databaseId`, das ist ungültig; keine `gh api --arg`).
  - macOS: `codesign --force --deep --sign - dist/SePlayer.app` + `codesign --verify --deep --strict`, DMG mit Applications-Symlink (`hdiutil ... -format UDZO`), `xattr -cr` + DMG ad-hoc signieren.
- Version steht in `seplayer/__init__.py` (`__version__`) und erscheint im **Fenstertitel** + Hilfe→Über. Artefakt-Dateinamen enthalten die Version.
- **Binaries bauen automatisch** bei jedem Push auf main und jedem Tag `v*` — der Nutzer muss nichts manuell im Actions-Tab starten („Run workflow" nur für Ausnahmen). Downloads: https://github.com/thesepix/SePlayer/releases
- macOS: DMG einmalig öffnen, `SePlayer.app` per Drag&Drop in den Programme-Ordner ziehen, danach normal starten. Ad-hoc signiert; der einmalige Gatekeeper-Hinweis (Rechtsklick→Öffnen bzw. „Trotzdem öffnen") ist ohne kostenpflichtige Apple-Notarisierung nicht vermeidbar. Windows: SmartScreen → „Weitere Informationen" → „Trotzdem ausführen".

## 2. Dateiaufbau

- `se_player.py` — Einstieg (`main()` mit `report_callback_exception` → Fehler-Dialog).
- `seplayer/__init__.py` — `__version__`.
- `seplayer/audio.py` — `PlaybackEngine` (pygame.mixer): **wichtig:** in gepackten Builds (`sys.frozen`) wird vor `import pygame` `SDL_VIDEODRIVER=dummy` gesetzt (sonst „video system not initialized" beim Start in exe/app — das war der große Startfehler); Init fängt ALLE Exceptions (auch `NotImplementedError`); eigene Uhr für Position; `END_EVENT`; `free_file(path, new_path=None)`-Contextmanager: spielende Datei wird ~20 ms durch stille Temp-WAV ersetzt (Handle frei), danach am (neuen) Pfad an letzter Position nahtlos fortgesetzt; wenn Datei weg → sauberer Stop; `pygame.event.get()` nach Resume leeren (sonst springt Wiedergabe auf nächsten Track).
- `seplayer/tags.py` — Metadaten/Rating/Cover lesen+schreiben (MP3: ID3 `POPM` + TXXX `RATING MM`; FLAC/OGG: `RATING`, `RATING WMP`, `FMPS_RATING`; WAV: ID3 via `add_tags` + RIFF-INFO-Fallback `_read_riff_info` (INAM/IART/...)). Skalen 0-5/0-100/0-255 werden auto-normalisiert. `_save_audio`/`_save_tag`: 3× Retry + chmod bei PermissionError; WinError 32/183-Retry; lange Windows-Pfade via `\?\` (`_open_path`); `last_error` global.
- `seplayer/state.py` — `state.json` im plattform Config-Dir (Windows `%APPDATA%/SePlayer/`): geometry, sashes, last_folder, favorites, columns, theme, autoload_last, volume, loop_mode. `config_dir()` liefert das Verzeichnis (wird auch fürs Log genutzt).
- `seplayer/theme.py` — Hell/Dunkel-Paletten, DWM-Dark-Titlebar (win32), `style_tk_widget` (pro Option try/except!), `style_menu`, `style_toplevel`.
- `seplayer/util.py` — `apply_filename_pattern` (Auto-Organize: `##`/`#`/`<feld>`/Feldname, Sanitize `\/:*?"<>|`), `title_from_filename` (Reparatur: `02 - Artist - Titel.mp3` → `Titel`), `format_time/size`, `stars_text`, `resource_path`.
- `seplayer/gui.py` — `SePlayerApp`: Favoriten-Pane, Ordnerbaum (lazy populate), Titelliste (Multi-Select, Drag-Select, Ctrl+A, Enter=Play, Inline-Edit nach 300 ms, Sterne per Klick nur bei Einfachauswahl), Spalten (Rechtsklick-Kopf: ein/ausblenden + Drag-Reorder), Kontextmenü (Sterne, Eigenschaften, Auto-Organize, **Titel aus Dateiname übernehmen**, Konvertieren, Im Explorer/Finder öffnen, Abspielen), Play-Queue unabhängig vom angezeigten Ordner, Loop (aus/alle/einer, persistiert), orange Markierung des spielenden Titels, Tray, **Type-Ahead** (s. §5), **Suche** (s. §6), `goto_track`, `_debug_log`.
- `seplayer/properties.py` — Eigenschaften-Dialog (Tabs/Details/Bewertungsfelder/Cover); Mehrfachauswahl: `plan_save` schreibt nur geänderte Felder (Prefill gemeinsamer Wert sonst leer) — verhindert Titel-Überschreiben.
- `seplayer/organize.py` — Auto-Organize-Dialog (Muster, Live-Preview, Kollisions-Suffix ` (n)`); ruft `guard=engine.free_file(path, target)` auf → Umbenennen des spielenden Tracks funktioniert nahtlos; `on_done` (Reload) läuft in `finally`.
- `seplayer/convert.py` — WAV→FLAC/MP3 via gebündeltem ffmpeg (`find_ffmpeg`: imageio-ffmpeg → frozen glob → PATH).
- `seplayer/search.py` — Such-Dialog (Strg+F): rekursiv ab Ordner, Dateiname + Tags (Titel/Interpret/Album/Genre), max. 500 Treffer, Stop-Button, Doppelklick → `app.goto_track(path, play=True)`.
- `seplayer/preferences.py` — Einstellungen (Theme hell/dunkel, Autoload, Lautstärke).
- `seplayer/tray.py` — pystray-Tray (Daemon-Thread, `root.after(0, fn)`-Marshaling; Klick = Play/Pause; Menü prev/next/stop/Fenster zeigen/Beenden).
- `seplayer/assets/` — S-Icon (schwarz/weiß/ico), 28-px-Overlay unten rechts + Fenster-/Taskleisten-Icon.
- `README.md` — Feature-Doku + Installationshinweise. **`HANDOVER.md`** — diese Datei.

## 3. Versionshistorie (kompakt)

- v1.0.0–1.0.2: erste App + CI; Start-Crash „video system not initialized" (Display vor Mixer).
- v1.1.0: Favoriten, state.json, konfigurierbare Spalten, Eigenschaften-Dialog, Multi-Rating-Felder.
- v1.2.x: „Im Explorer/Finder öffnen", Cover-Tab.
- v1.3.0–1.3.4: Multi-Select, Enter=Play, Preferences, Spalten-Menü + Drag-Reorder, Auto-Organize, Klick-Seek, Inline-Edit, globaler Fehler-Popup, Reload nach Rename.
- v1.3.5–1.3.8: WAV/AIFF-ID3-Rating, spielende Zeile orange, Ctrl+A, 1-Klick-Sterne, CI-Quota-Fix (retention 3 + continue-on-error), YAML-Kolonnen-Bug.
- v1.3.9–1.3.11: Type-Ahead im Baum (v1.3.9 ging durch Sandbox-Wipe verloren; v1.3.11 mit grep-Verify neu). **Wichtig: Sandbox wischt `/workspace` zwischen Nachrichten — nie uncommittete Änderungen über Tool-Calls hinweg vertrauen.**
- v1.3.12: Queue unabhängig vom Ordner; Loop-Button.
- v1.3.13: S-Logo (icon.png/icon_dark.png/icon.ico) als exe-/Fenster-/Tray-Icon; Type-Ahead-FS-Fallback.
- v1.3.14–1.3.17: CI-Release-Cleanup debuggt (bash statt PowerShell; `gh api releases?id`; kein `--arg`); nur neuestes Release bleibt.
- v1.3.18/19: Type-Ahead auf Widget-Ebene; WAV-RIFF-INFO; Konvertieren (ffmpeg gebündelt).
- v1.3.20: Multi-Edit schreibt nur geänderte Felder (Titel-Bug behoben).
- v1.3.21: Type-Ahead-Puffer im Rahmen-Titel („Ordner „v““).
- v1.3.22: Tray-Icon (pystray).
- v1.3.23: Drag-Select-Fix (Zeiger über erster Zeile).
- v1.3.24/25: `free_file` gehärtet (Temp-WAV, Retry WinError 32/183, chmod+Retry bei PermissionError).
- v1.3.26: stale END_EVENT nach Resume verwerfen; Stille-WAV 20 ms.
- v1.3.27: Sterne per Klick in Bewertungs-Spalte nur bei Einfachauswahl (Mehrfachauswahl nur via Rechtsklick).
- **v1.3.28: Start-Crash in gepackten Builds behoben** — `sys.frozen` → `SDL_VIDEODRIVER=dummy` (GUI ist tkinter, Video nur für Event-Queue); breite `except Exception` überall in der Audio-Init; macOS-CI verifiziert Signatur + signiert DMG; README: Builds laufen automatisch.
- v1.3.29: Type-Ahead umgebaut (bind_all, fokusabhängig: Baum/Titelliste/Favoriten); **Suche (Strg+F)**; **„Titel aus Dateiname übernehmen"** im Kontextmenü.
- v1.3.30: Auto-Organize während Wiedergabe gefixt — `free_file(path, new_path)` spielt umbenannten spielenden Track am neuen Namen nahtlos weiter (vorher: Abbruch + nächster Track + „Datei nicht gefunden"); `on_done` in `finally`; klare „Datei nicht gefunden"-Meldung.
- v1.3.31: Type-Ahead grundlegend repariert + **headless per Xvfb getestet**: `_ensure_populated` (programmatic `open=True` feuert KEIN `<<TreeviewOpen>>` → Platzhalter „…" blieb stehen), Suchreihenfolge: Kinder des Knotens → Geschwister → alle geladenen Knoten (BFS) → Dateisystem des aktuellen Ordners; KeyPress doppelt gebunden mit Serial-Dedupe; keine doppelten Kinder in `_populate_node`.
- v1.3.32: Type-Ahead-Diagnose-Log: jede Taste nach `<Config>/SePlayer/typeahead.log` (Windows: `%APPDATA%\SePlayer\typeahead.log`, wird bei >512 KB geleert); dritte KeyPress-Ebene (root/toplevel); keysym-Fallback.
- v1.3.33: `_on_global_key` komplett in try/except — Fehler landen als Traceback im Log statt als Popup.

## 4. Prozess-Regeln (WICHTIG für die nächste KI)

1. **Sandbox wischt `/workspace` zwischen User-Nachrichten.** Immer zuerst: `cd /workspace/github__thesepix__SePlayer && git fetch -q origin && git reset -q --hard origin/main`. Patch + grep-Verify + AST + `py_compile` + commit + push + tag in **einem einzigen bash-Kommando** ausführen — nie uncommittete Änderungen über Nachrichten hinweg retten wollen (mehrfach verloren gegangen).
2. Push: `git -c "credential.helper=!f() { echo username=thesepix; echo password=\$GH_TOKEN; }; f" push origin main` (Dasselbe für Tags). `gh` ist authentifiziert für Reads und git-push; **mutierende REST-Aufrufe sind blockiert** („Mutating GitHub API calls are not allowed"), curl ist blockiert. CI-GITHUB_TOKEN löscht Releases.
3. **Tags nur frisch anlegen** (`git tag vX.Y.Z && push origin vX.Y.Z`), nie löschen/re-pushen (erzeugt „No jobs were run"-Mails, die den Nutzer nerven).
4. Vor Commit: `python3 -m py_compile se_player.py seplayer/*.py`, AST-Parse aller Dateien, `yaml.safe_load` auf dem Workflow, grep-Verify, dass das Patch wirklich im File ist.
5. Version bumpen in `seplayer/__init__.py`; Commit-Msg auf Deutsch mit `vX.Y.Z: ...`; dann Tag + pushen; CI-Run abwarten (~2–4 min) und Release-Assets prüfen: `gh run list --repo thesepix/SePlayer --limit 2 --json databaseId,headBranch,status,conclusion` und `gh api repos/thesepix/SePlayer/releases/tags/vX.Y.Z --jq '[.assets[].name]'`.
6. Nie neue Repos anlegen. Dateien werden nur über Push ins bestehende Repo ausgeliefert.

## 5. OFFEN: Type-Ahead funktioniert auf dem Windows-PC des Nutzers nicht

- **Erwartung (abgesprochen):** Ordner im Baum markiert (z. B. „Funckarma - Solid State (Fall version)"), Taste „r" tippen → Sprung zum nächsten Geschwister-Ordner mit „r" („RJELEVEN - The Remixes Vol.5 - in dispute"). Puffer erscheint im linken Rahmen-Titel als „Ordner „r“" (900 ms). Case-insensitiv.
- **Stand:** In headless Xvfb-Simulation (echte App, echte tkinter 8.6, `event_generate`) mit exakt diesen Ordnernamen verifiziert: Klick Funckarma → „r" → landet auf RJELEVEN. Log: `key='r' focus=Tk state=0x0 -> typeahead buf` / `typeahead buf='r' start='Funckarma...' target='RJELEVEN...'`. Nutzer testete zuletzt **v1.3.31** (Screenshot-Titel) und sah „nichts passiert".
- **Nächster Schritt (bereits an Nutzer kommuniziert):** v1.3.33 laden (Titelleiste prüfen!), im Baum Funckarma anklicken, „r" tippen, dann Log `%APPDATA%\SePlayer\typeahead.log` (Win+R → Pfad → Enter) — letzte ~10 Zeilen schicken + melden, ob der Rahmen-Titel „Ordner „r“" anzeigt und ob die Auswahl springt.
- **Log interpretieren:** `key='r' ... -> typeahead buf` + `target=...` = Taste kommt an und Sprung wird berechnet; **keine `key=`-Zeilen** = Tastendruck erreicht die App nicht (Fokus/Stale-Exe); `ignoriert: ...` = Grund steht dabei (Dialog offen / Textfeld / Strg+Alt); `FEHLER in _on_global_key:` + Traceback = echter Fehler auf seinem System.
- Bekannte Tk-Fallen (bereits adressiert): root-Binding wird von Treeview-Klassen-Binding gebrochen → deshalb bind_all + root + Widget-Bindings mit Serial-Dedupe; programmatisches `open=True` feuert kein `<<TreeviewOpen>>` → `_ensure_populated` lädt Kinder beim Auswählen/Öffnen nach.

## 6. Headless-Test-Rezept im Sandbox (funktioniert, für Reproduktionen)

Ohne root: `apt-get -o Dir::State::Lists=/tmp/apt/lists -o Dir::Cache=/tmp/apt/cache -o Dir::State::status=/tmp/apt/state/status -o APT::Get::AllowUnauthenticated=true update` und `... install --download-only -y xvfb libtk8.6 libtcl8.6 fontconfig-config fonts-dejavu-core`, dann alle debs mit `dpkg -x` nach `/tmp/xroot`. Xvfb-Binary patchen (`/usr/bin\0` → `/tmp/x\0\0\0`, xkbcomp nach `/tmp/x/xkbcomp`), starten: `LD_LIBRARY_PATH=/tmp/xroot/usr/lib/x86_64-linux-gnu /tmp/Xvfb :99 -screen 0 1280x800x24 -ac -xkbdir /tmp/xroot/usr/share/X11/xkb &`. Test-App mit: `DISPLAY=:99 LD_LIBRARY_PATH=/tmp/xroot/usr/lib/x86_64-linux-gnu TCL_LIBRARY=/tmp/xroot/usr/share/tcltk/tcl8.6 TK_LIBRARY=/tmp/xroot/usr/share/tcltk/tk8.6 FONTCONFIG_FILE=/tmp/fonts.conf python3 test.py` (fonts.conf mit `<dir>/tmp/xroot/usr/share/fonts</dir>` + `<cachedir>/tmp/fccache</cachedir>`). Events simulieren via `widget.event_generate("<KeyPress>", keysym="r")` bzw. `event_generate("<Button-1>", x=.., y=..)` auf `tree.bbox(item)`. pygame lokal ohne Audio → `available=False`, stört nicht; pystray meckert ohne Tray („Failed to dock icon") — harmlos, wird in gui gecatcht.

## 7. Weitere offene Punkte

- Nutzer muss noch ~97 alte Actions-Artefakte manuell löschen (Sandbox-Token darf nicht): Repo → Settings → Actions → General → Retention **1 Tag** (wirkt rückwirkend). Alte Releases werden bereits automatisch gelöscht.
- „Titel aus Dateiname übernehmen" (v1.3.29) ist genau dafür gedacht, die durch den Pre-v1.3.20-Multi-Edit-Bug überschriebenen Titel zu reparieren: alle Tracks markieren → Rechtsklick → „Titel aus Dateiname übernehmen".
- macOS: erster Start nach Download einmalig Rechtsklick→Öffnen (ad-hoc signiert, nicht notarisiert). Linux: Tray braucht AppIndicator.
- Immer dem Nutzer sagen: Version im **Dateinamen UND Fenstertitel** prüfen (z. B. „SePlayer 1.3.33“), nie alte Exe testen.

## 8. CI-/Release-Check (Copy&Paste)

```bash
gh run list --repo thesepix/SePlayer --limit 2 --json databaseId,headBranch,status,conclusion
gh api repos/thesepix/SePlayer/releases/tags/v1.3.33 --jq '"release \(.tag_name): " + ([.assets[].name]|join(", "))'
```
Release-URL-Muster: https://github.com/thesepix/SePlayer/releases/tag/vX.Y.Z

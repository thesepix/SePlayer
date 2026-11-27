# SePlayer — Handover / Kontext für die nächste KI

**Repo:** `thesepix/SePlayer` (**PUBLIC** — alles inkl. dieser Datei ist öffentlich sichtbar) · **Aktueller Stand:** `v1.3.33` (Tag + Release vorhanden, CI grün)
**Projekt:** privater Desktop-Musikplayer (MediaMonkey-artig) für Windows/macOS/Linux.
**Nutzer:** deutschsprachig, testet primär auf einem Windows-PC, auch Mac. Mag robuste Datei-Sperr-Behandlung
(Umbenennen/Beschreiben während der Wiedergabe), versionierte Binaries (nie „welche Version teste ich gerade?"),ärgert sich über CI-Benachrichtigungs-Mails und über das Testen staler Exes.

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

## 3. Versionshistorie

→ siehe [CHANGELOG.md](CHANGELOG.md) (neueste oben). Release-Regel: Version bumpen → Commit `vX.Y.Z: …` → push main → Tag `vX.Y.Z` pushen (nie löschen/re-pushen).

## 3a. Aktueller Arbeitsstand (vor jeder Aufgabe ausfüllen, nach jedem Teilschritt aktualisieren)

**Aktuelle Aufgabe:** Type-Ahead im Ordnerbaum auf dem Windows-PC des Nutzers debuggen.
- Ziel: Funckarma im Baum markiert → „r“ tippen → Sprung auf RJELEVEN (nächster „r“-Geschwister).
- Plan: Nutzer testet v1.3.33, wertet `typeahead.log` aus (§5), dann fixen.
- Betroffene Dateien: `seplayer/gui.py` (Type-Ahead), ggf. `tests/test_gui_typeahead.py`.
- Status: **wartet auf `typeahead.log` von v1.3.33** (`%APPDATA%\SePlayer\typeahead.log`, letzte ~10 Zeilen nach dem Tippen).

## 3b. Versucht und gescheitert (nicht wiederholen)

- Root-weites KeyPress-Binding: wird von der Treeview-Klassen-Binding gebrochen → deshalb bind_all + root + Widgets mit Serial-Dedupe.
- Nur Widget-Bindings (v1.3.18–28): auf manchen Systemen unzuverlässig.
- Sibling-first-Suchreihenfolge (v1.3.29): falsches Ziel → jetzt Kinder des Knotens zuerst.
- Programmatisches `open=True` feuert KEIN `<<TreeviewOpen>>` → `_ensure_populated` lädt Kinder nach.
- „video system not initialized“ in gepackten Builds → `SDL_VIDEODRIVER=dummy` bei `sys.frozen` (v1.3.28).
- `gh release list --json databaseId` und `gh api --arg` sind ungültig; CI-Cleanup braucht `shell: bash` + `gh api …/releases?id`.
- Multi-Edit vor v1.3.20 überschrieb die Titel aller markierten Tracks → `plan_save` schreibt nur geänderte Felder.
- v1.3.9-Type-Ahead ging durch Sandbox-Wipe verloren → immer in einem Schritt committen.

## 3c. Letzter bekannt guter Stand

- **v1.3.33** (Tag + Release, CI grün, Commit `7977d57`); Doku/Standards danach: `5a9960e`. Zurückgehen: `git checkout v1.3.33`.

## 4. Prozess-Regeln (allgemeingültig — funktionieren mit jedem Werkzeug)

1. Kleine, häufige Commits; **main bleibt immer lauffähig** — Unfertiges auf Branch `wip/<thema>`.
2. Vor jedem Commit nur: **`python3 tools/check.py`** (py_compile + AST + Workflow-YAML + Unit-Tests; GUI-Test nur mit DISPLAY, sonst skip — Rezept in `tests/README.md`).
3. Patch per grep im File verifizieren (nicht blind vertrauen).
4. Version bumpen in `seplayer/__init__.py`; Commit `vX.Y.Z: …` auf Deutsch; push `main`; `git tag vX.Y.Z && git push origin vX.Y.Z`. **Nie Tags löschen/re-pushen.** Nie neue Repos anlegen.
5. CI baut automatisch bei jedem Push auf `main` und jedem Tag `v*`; prüfen mit den Befehlen in §8.
6. Offene Punkte/Bugs zusätzlich als **GitHub-Issues** tracken (brauchen Schreibzugriff) — in HANDOVER.md nur verlinken.
7. Requirements sind gepinnt (`requirements.txt`, `requirements-build.txt`), Python-Version in `.python-version`.

### Umgebungsnotizen (nur diese eine Sandbox-Umgebung — NICHT allgemeingültig; keine Credentials in öffentlichen Dateien)

- Diese Sandbox wischt `/workspace` zwischen Nachrichten → immer zuerst `git fetch -q origin && git reset -q --hard origin/main`; Patch + `tools/check.py` + Commit + Push in **einem** bash-Kommando.
- Push aus dieser Sandbox nur mit lokal hinterlegten Git-Credentials; das Umgebungs-Token erlaubt **keine mutierenden REST-Aufrufe** (Issues/PRs/Visibility/Merges gehen darüber nicht) und curl ist blockiert.

## 5. OFFEN: Type-Ahead funktioniert auf dem Windows-PC des Nutzers nicht

- **Erwartung (abgesprochen):** Ordner im Baum markiert (z. B. „Funckarma - Solid State (Fall version)"), Taste „r" tippen → Sprung zum nächsten Geschwister-Ordner mit „r" („RJELEVEN - The Remixes Vol.5 - in dispute"). Puffer erscheint im linken Rahmen-Titel als „Ordner „r“" (900 ms). Case-insensitiv.
- **Stand:** In headless Xvfb-Simulation (echte App, echte tkinter 8.6, `event_generate`) mit exakt diesen Ordnernamen verifiziert: Klick Funckarma → „r" → landet auf RJELEVEN. Log: `key='r' focus=Tk state=0x0 -> typeahead buf` / `typeahead buf='r' start='Funckarma...' target='RJELEVEN...'`. Nutzer testete zuletzt **v1.3.31** (Screenshot-Titel) und sah „nichts passiert".
- **Nächster Schritt (bereits an Nutzer kommuniziert):** v1.3.33 laden (Titelleiste prüfen!), im Baum Funckarma anklicken, „r" tippen, dann Log `%APPDATA%\SePlayer\typeahead.log` (Win+R → Pfad → Enter) — letzte ~10 Zeilen schicken + melden, ob der Rahmen-Titel „Ordner „r“" anzeigt und ob die Auswahl springt.
- **Log interpretieren:** `key='r' ... -> typeahead buf` + `target=...` = Taste kommt an und Sprung wird berechnet; **keine `key=`-Zeilen** = Tastendruck erreicht die App nicht (Fokus/Stale-Exe); `ignoriert: ...` = Grund steht dabei (Dialog offen / Textfeld / Strg+Alt); `FEHLER in _on_global_key:` + Traceback = echter Fehler auf seinem System.
- Bekannte Tk-Fallen (bereits adressiert): root-Binding wird von Treeview-Klassen-Binding gebrochen → deshalb bind_all + root + Widget-Bindings mit Serial-Dedupe; programmatisches `open=True` feuert kein `<<TreeviewOpen>>` → `_ensure_populated` lädt Kinder beim Auswählen/Öffnen nach.

## 6. Headless-Test-Rezept (Xvfb) — jetzt versioniert in `tests/README.md`

Massgeblich: `tests/README.md` + `tests/test_gui_typeahead.py` (+ `tools/check.py`). Kurzfassung:

Ohne root: `apt-get -o Dir::State::Lists=/tmp/apt/lists -o Dir::Cache=/tmp/apt/cache -o Dir::State::status=/tmp/apt/state/status -o APT::Get::AllowUnauthenticated=true update` und `... install --download-only -y xvfb libtk8.6 libtcl8.6 fontconfig-config fonts-dejavu-core`, dann alle debs mit `dpkg -x` nach `/tmp/xroot`. Xvfb-Binary patchen (`/usr/bin\0` → `/tmp/x\0\0\0`, xkbcomp nach `/tmp/x/xkbcomp`), starten: `LD_LIBRARY_PATH=/tmp/xroot/usr/lib/x86_64-linux-gnu /tmp/Xvfb :99 -screen 0 1280x800x24 -ac -xkbdir /tmp/xroot/usr/share/X11/xkb &`. Test-App mit: `DISPLAY=:99 LD_LIBRARY_PATH=/tmp/xroot/usr/lib/x86_64-linux-gnu TCL_LIBRARY=/tmp/xroot/usr/share/tcltk/tcl8.6 TK_LIBRARY=/tmp/xroot/usr/share/tcltk/tk8.6 FONTCONFIG_FILE=/tmp/fonts.conf python3 test.py` (fonts.conf mit `<dir>/tmp/xroot/usr/share/fonts</dir>` + `<cachedir>/tmp/fccache</cachedir>`). Events simulieren via `widget.event_generate("<KeyPress>", keysym="r")` bzw. `event_generate("<Button-1>", x=.., y=..)` auf `tree.bbox(item)`. pygame lokal ohne Audio → `available=False`, stört nicht; pystray meckert ohne Tray („Failed to dock icon") — harmlos, wird in gui gecatcht.

## 7. Weitere offene Punkte (zusätzlich als GitHub-Issues anlegen — Schreibzugriff nötig)

- [ ] Issue anlegen: „Type-Ahead im Ordnerbaum funktioniert auf Windows nicht“ (siehe §5; Log auswerten, sobald vorhanden)


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

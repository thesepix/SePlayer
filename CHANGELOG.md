# CHANGELOG — SePlayer

Format: pro Version ein Abschnitt; neueste oben. Release-Regel: Version in `seplayer/__init__.py` bumpen,
Commit `vX.Y.Z: …`, push `main`, dann `git tag vX.Y.Z && git push origin vX.Y.Z` (CI baut + released;
Tags nie löschen/re-pushen). Nie unfertiges auf `main` — WIP auf Branch `wip/<thema>`.

## v1.3.33
- `_on_global_key` komplett in try/except — Fehler landen als Traceback im `typeahead.log` statt als Popup.

## v1.3.32
- Type-Ahead-Diagnose-Log: jede Taste nach `<Config>/SePlayer/typeahead.log` (Windows: `%APPDATA%\SePlayer\typeahead.log`);
  dritte KeyPress-Ebene (Toplevel), keysym-Fallback.

## v1.3.31
- Type-Ahead repariert + headless (Xvfb) getestet: `_ensure_populated` (programmatic `open=True` feuert kein
  `<<TreeviewOpen>>`), Reihenfolge: Kinder des Knotens → Geschwister → alle geladenen Knoten (BFS) → Dateisystem;
  KeyPress doppelt gebunden mit Serial-Dedupe; keine doppelten Kinder in `_populate_node`.

## v1.3.30
- Auto-Organize während Wiedergabe: `free_file(path, new_path)` spielt umbenannten spielenden Track am neuen
  Namen nahtlos weiter; `on_done` in `finally`; klare „Datei nicht gefunden"-Meldung.

## v1.3.29
- Type-Ahead umgebaut (bind_all, fokusabhängig: Baum/Titelliste/Favoriten); Suche (Strg+F, `seplayer/search.py`);
  „Titel aus Dateiname übernehmen" im Kontextmenü (`util.title_from_filename`).

## v1.3.28
- Start-Crash in gepackten Builds behoben: `sys.frozen` → `SDL_VIDEODRIVER=dummy`; Audio-Init fängt alle
  Exceptions; macOS-CI verifiziert ad-hoc-Signatur + signiert DMG; Builds laufen automatisch (kein manuelles Run workflow).

## v1.3.27
- Sterne per Klick in der Bewertungs-Spalte nur bei Einfachauswahl (Mehrfachauswahl nur via Rechtsklick-Menü).

## v1.3.26
- Stale END_EVENT nach Resume verwerfen (sonst Sprung auf nächsten Track); Stille-WAV auf 20 ms.

## v1.3.24–v1.3.25
- `free_file` gehärtet: echte Temp-WAV, Retry bei WinError 32/183, 3× Retry + chmod bei PermissionError.

## v1.3.23
- Drag-Select-Fix (Zeiger über erster Zeile → Zeile 0).

## v1.3.22
- Tray-Icon (pystray): Klick = Play/Pause, Menü prev/next/stop/Fenster/Beenden.

## v1.3.21
- Type-Ahead-Puffer im Rahmen-Titel („Ordner „v“").

## v1.3.20
- Multi-Edit schreibt nur geänderte Felder (`plan_save`) — Titel werden nicht mehr überschrieben.

## v1.3.18–v1.3.19
- Type-Ahead auf Widget-Ebene; WAV-RIFF-INFO-Fallback; Konvertieren (WAV→FLAC/MP3 via gebündeltem ffmpeg).

## v1.3.14–v1.3.17
- CI-Release-Cleanup (bash, `gh api releases?id`); nur neuestes Release bleibt; Artefakt-Retention 3 Tage + continue-on-error.

## v1.3.13
- S-Logo (icon.png/icon_dark.png/icon.ico) als exe-/Fenster-/Tray-Icon; Type-Ahead-FS-Fallback.

## v1.3.12
- Play-Queue unabhängig vom angezeigten Ordner; Loop-Button (aus/alle/einer, persistiert).

## v1.3.9–v1.3.11
- Type-Ahead im Ordnerbaum (v1.3.9 ging durch Sandbox-Wipe verloren, v1.3.11 mit grep-Verify neu eingebracht).

## v1.3.5–v1.3.8
- WAV/AIFF-ID3-Rating; spielende Zeile orange; Strg+A; 1-Klick-Sterne in der Bewertungs-Spalte; CI-Quota-Fix; YAML-Kolonnen-Bug.

## v1.3.0–v1.3.4
- Multi-Select, Enter=Play, Preferences (Theme/Autoload/Volume), Spalten-Menü + Drag-Reorder, Auto-Organize
  (`## - artist - title`), Klick-Seek, Inline-Zell-Edit, globaler Fehler-Popup, Reload nach Rename.

## v1.2.x
- „Im Explorer/Finder öffnen" im Kontextmenü; Cover-Tab in den Eigenschaften.

## v1.1.0
- Favoriten, persistierter Zustand (state.json: Geometrie/Sashes/letzter Ordner/Spalten), konfigurierbare Spalten,
  Eigenschaften-Dialog (Tags/Details/Bewertungsfelder), Multi-Rating-Felder (POPM + TXXX RATING MM; FLAC/OGG RATING,
  RATING WMP, FMPS_RATING).

## v1.0.0–v1.0.2
- Erste Version + CI (exe/dmg/linux); Start-Crash „video system not initialized" gefixt (Display vor Mixer).

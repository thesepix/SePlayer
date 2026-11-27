# CONTRIBUTING — Mitmachen an SePlayer

Danke fürs Interesse! SePlayer ist ein Desktop-Musikplayer in Python (tkinter + pygame + mutagen). KI-Agenten: bitte zusätzlich `AGENTS.md` und `HANDOVER.md` lesen.

## Setup (Entwicklung)

```bash
python3 -m venv venv
source venv/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 se_player.py            # Dev-Start (Linux/macOS: ggf. DISPLAY nötig)
```

Python 3.10+ (CI nutzt 3.12). Auf dem Mac am besten Python von python.org (bringt tkinter mit).

## Lokale Binaries bauen (wie CI)

```bash
pip install -r requirements-build.txt
pyinstaller se_player.spec --noconfirm --clean
# Ergebnis: dist/SePlayer.exe (Windows) | dist/SePlayer.app (macOS) | dist/SePlayer (Linux)
# macOS-DMG: hdiutil create -volname SePlayer -srcfolder dist/SePlayer.app -ov dist/SePlayer.dmg
```

## Vor jedem Commit

- **`python3 tools/check.py`** muss „ALL CHECKS OK“ ausgeben (py_compile + AST + Workflow-YAML + Unit-Tests; GUI-Test nur mit DISPLAY, Rezept in `tests/README.md`).
- Patch per grep im File verifizieren (nicht blind vertrauen).
- Python-Version: `.python-version` (3.12); Requirements sind gepinnt.
- Manuell testen: Start, Ordnerbaum, Wiedergabe, Tags schreiben, Dark Mode — Version im Fenstertitel notieren.

## Commits, Branches, PRs

- Commit-Messages auf Deutsch, prägnant: `vX.Y.Z: <Was wurde geändert und warum>` (Version nur beim Release-Bump in `seplayer/__init__.py`).
- Kleine Branches/PRs; PR-Template (`.github/PULL_REQUEST_TEMPLATE.md`) ausfüllen; bei Bugfixes Issue verlinken (`Closes #…`).
- Releases entstehen automatisch über Tags `vX.Y.Z` (CI baut exe/dmg/linux und veröffentlicht ein Release). Tags nie löschen/re-pushen.

## Issues

- Bugs über `.github/ISSUE_TEMPLATE/bug_report.md` melden — wichtig: **SePlayer-Version aus dem Fenstertitel** (z. B. „SePlayer 1.3.33"), Betriebssystem, Repro-Schritte, Screenshots, relevante Logs (`%APPDATA%\SePlayer\*.log` unter Windows).
- Features über `feature_request.md`.

## Code-Stil

- Python, UTF-8, 4 Spaces, LF (`.editorconfig`).
- UI-Texte/Docstrings deutsch, Bezeichner englisch.
- Keine Build-Artefakte committen (`build/`, `dist/`, `__pycache__/` sind ignoriert).
- Fehlerbehandlung: GUI-Callbacks über `report_callback_exception` (Popup); pygame/Datei-Zugriffe breit absichern (`except Exception`), nie den App-Start crashen lassen.

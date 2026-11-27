# AGENTS.md — Regeln für KI-Agenten (Claude, Codex, Copilot & Co.)

Dieses Repo ist **SePlayer**: privater Desktop-Musikplayer (Python 3.12, tkinter-GUI + pygame-Audio + mutagen).
**Vor jeder Arbeit zuerst lesen:** `HANDOVER.md` (vollständiger Kontext: Architektur, Historie v1.0.0–aktuell, offene Punkte)
und `CONTRIBUTING.md` (Setup, Build, PR-Prozess). Hier nur die Kurzfassung.

## Schnellstart

```bash
python3 -m venv venv && source venv/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 se_player.py                            # Dev-Start
```

Lokaler Binary-Build (gleich wie CI):

```bash
pip install -r requirements-build.txt
pyinstaller se_player.spec --noconfirm --clean  # -> dist/SePlayer(.exe/.app)
```

Vor **jedem** Commit nur: **`python3 tools/check.py`** (py_compile + AST + Workflow-YAML + Unit-Tests; GUI-Test nur mit DISPLAY — Rezept `tests/README.md`). Ausserdem Patch per grep im File verifizieren.

## Versioning & Releases

- Version steht in `seplayer/__init__.py` (`__version__`) und erscheint im **Fenstertitel** (z. B. „SePlayer 1.3.33").
- Release-Flow: Version bumpen → Commit `vX.Y.Z: <deutsch, prägnant>` → push `main` → `git tag vX.Y.Z && git push origin vX.Y.Z`.
  **Nie Tags löschen oder erneut pushen** (erzeugt „No jobs were run"-Mails). Nie neue Repos anlegen.
- CI baut automatisch bei jedem Push auf `main` und jedem Tag `v*` (exe/dmg/linux, Release mit versionierten Dateinamen).
- CI/Release prüfen: `gh run list --repo thesepix/SePlayer --limit 2 --json databaseId,headBranch,status,conclusion` und
  `gh api repos/thesepix/SePlayer/releases/tags/vX.Y.Z --jq '[.assets[].name]'`

## Arbeitsweise

- **main bleibt immer lauffähig**: Unfertiges auf Branch `wip/<thema>`; fertiges als kleiner Commit auf `main` oder Feature-Branch + PR (Template `.github/PULL_REQUEST_TEMPLATE.md` ausfüllen, PRs in-place updaten, nie Branches/PRs anderer löschen).
- Versionshistorie in `CHANGELOG.md`; Python-Version in `.python-version`; Requirements gepinnt.
- Build-Artefakte (`build/`, `dist/`, `__pycache__/`) nie committen — stehen in `.gitignore`.
- GUI-Bugs wenn möglich headless per Xvfb reproduzieren und mit `event_generate` testen — Rezept in `HANDOVER.md` §6.
- Bekannte Fallen (nicht „fixen", sind so gewollt):
  - In gepackten Builds setzt `seplayer/audio.py` bei `sys.frozen` `SDL_VIDEODRIVER=dummy` (verhindert „video system not initialized").
  - Windows-Dateisperre beim Umbenennen/Beschreiben spielender Dateien läuft über `engine.free_file(path, new_path)` (Stille-Temp-WAV-Trick) — immer diesen Guard verwenden.
  - UI-Texte und Docstrings sind **deutsch**, Code/Variablen englisch, UTF-8, 4 Spaces (s. `.editorconfig`).

## Offene Punkte

- Siehe `HANDOVER.md` §5 (Type-Ahead im Ordnerbaum auf Windows — Diagnose über `typeahead.log` im Config-Dir, z. B. `%APPDATA%\SePlayer\typeahead.log`) und §7 (offene Aufgaben).

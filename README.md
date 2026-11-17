# MP3 Player

Desktop-Musikplayer für **Windows, macOS und Linux** — geschrieben in Python (tkinter-GUI + pygame-Audio), dadurch plattformübergreifend und ohne externen Player (wie VLC) nutzbar.

## Funktionen

- **Folder-basierter Datei-Browser:** links ein aufklappbarer Ordner-Baum der Festplatte
  (unter Windows werden alle Laufwerke als Wurzeln angezeigt, sonst `/` und das Home-Verzeichnis)
- **Dateiliste:** alle Audiodateien des gewählten Ordners in der Mitte, inkl. Tags
  (Titel, Interpret, Album, Dauer, Sternebewertung, Format/Bitrate), sortierbar per Klick auf die Spaltenköpfe
- **Album-Cover:** links unten wird das Cover des ausgewählten Albums angezeigt
- **Player-Leiste unten:** ⏮ Vorheriger, ▶/⏸ Play/Pause, ⏹ Stop, ⏭ Nächster, Fortschrittsbalken
  (klickbar zum Springen), Zeitanzeige (aktuell/gesamt), Lautstärke-Regler
- **Tags & Sternebewertungen (Popularimeter):** Anzeige der Bewertung als ★ in der Liste;
  Setzen/Entfernen per **Rechtsklick → „Sternebewertung setzen“**
  - MP3: ID3-`POPM`-Frame (Rating-Byte, 5 Sterne = 255)
  - FLAC/OGG: Vorbis-Comments `RATING` (0–100) und `FMPS_RATING` (0–5)
- **Flexibles Layout:** alle Bereiche über verschiebbare Trennlinien (PanedWindow) anpassbar
- **Tastenkürzel:** Leertaste = Play/Pause, → = nächster Titel, ← = vorheriger Titel
- Automatischer Wechsel zum nächsten Titel am Track-Ende

## Unterstützte Formate

Über SDL_mixer (in pygame enthalten): **MP3, FLAC, OGG/Vorbis, WAV, OPUS** (je nach System-Build).
FLAC und MP3 sind die priorisierten Formate und funktionieren überall.

Hinweis: M4A/AAC/WMA werden im Datei-Browser mit aufgeführt, können aber von SDL_mixer nicht
decodiert werden — beim Abspielen erscheint dann ein entsprechender Hinweis. Für diese Formate
wäre ein VLC-basierter Player nötig.

## Voraussetzungen

- Python 3.10 oder neuer — auf dem Mac am besten von https://www.python.org/downloads/
  (diese Installation bringt tkinter und pip mit; das macOS-System-python3 hat teils kein tkinter)
- Ein Ausgabegerät (Soundkarte) — logisch notwendig zum Abspielen

## Installation

```bash
pip3 install -r requirements.txt    # unter Windows meist: pip
```

## Start

```bash
python3 mp3_player.py               # unter Windows meist: python
```

## Mac: „zsh: command not found: pip / python"

macOS bringt `python` und `pip` nicht im PATH. Lösung mit `python3` und einem virtuellen Environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python mp3_player.py
```

Falls `python3` ebenfalls fehlt: Python 3 von python.org installieren und danach ein neues
Terminalfenster öffnen. Innerhalb des aktivierten venv funktionieren danach auch `python` und `pip`.

## Fertige Programmdateien (kein Python nötig)

Zum Starten wird **keine Python-Installation und keine PATH-Variable** gebraucht — es gibt
fertige Dateien pro System:

- **Windows:** `Mp3Player.exe` — Doppelklick genügt
- **macOS:** `Mp3Player.dmg` — DMG öffnen, App in den Programme-Ordner ziehen; beim ersten Start
  evtl. Rechtsklick → „Öffnen" (die App ist nicht signiert)
- **Linux:** `Mp3Player-linux-x86_64` — `chmod +x Mp3Player-linux-x86_64 && ./Mp3Player-linux-x86_64`
  (braucht glibc, auf den meisten Distributionen vorhanden)

Die Binaries werden bei jedem Push automatisch per **GitHub Actions** gebaut (als Artefakte des
Workflow-Runs). Ein Tag `v...` (z. B. `git tag v1.0.0 && git push origin v1.0.0`) veröffentlicht
zusätzlich ein **Release** mit allen drei Dateien als Download.

### Selbst bauen (auf dem jeweiligen System; Cross-Build geht nicht)

```bash
pip3 install -r requirements.txt -r requirements-build.txt
pyinstaller mp3_player.spec --noconfirm --clean
# Ergebnis in dist/:  Mp3Player.exe (Windows) | Mp3Player.app (macOS) | Mp3Player (Linux)
# macOS .app -> .dmg:  hdiutil create -volname Mp3Player -srcfolder dist/Mp3Player.app -ov dist/Mp3Player.dmg
```

## Bedienung

1. Links im Ordner-Baum einen Ordner aufklappen und anklicken (oder *Datei → Ordner öffnen …*)
2. In der Mitte per Doppelklick einen Titel starten
3. Unten über die Player-Leiste steuern; Fortschrittsbalken ziehen = Springen im Titel
4. Rechtsklick auf einen Titel → Sternebewertung (1–5 ★) setzen; wird in die Datei geschrieben (POPM/RATING)

## Projektstruktur

```
mp3-player/
├── mp3_player.py                # Startpunkt
├── mp3_player.spec              # PyInstaller-Spec (fertige Binaries: exe/app/linux)
├── requirements.txt             # Laufzeit-Abhängigkeiten (pygame, mutagen, Pillow)
├── requirements-build.txt       # Build-Abhängigkeiten (PyInstaller)
├── .github/workflows/build.yml  # automatischer Binary-Build (exe / dmg / linux)
├── README.md
└── mp3player/
    ├── __init__.py
    ├── audio.py                 # Wiedergabe-Engine (pygame.mixer)
    ├── tags.py                  # Tags lesen/schreiben, Sterne (POPM/RATING), Cover
    └── gui.py                   # tkinter-Oberfläche (Baum, Cover, Liste, Player-Leiste)
```

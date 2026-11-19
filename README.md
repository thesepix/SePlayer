# SePlayer

Desktop-Musikplayer für **Windows, macOS und Linux** — geschrieben in Python (tkinter-GUI + pygame-Audio). Als fertige Datei (exe/dmg/Linux-Binary) startbar **ohne Python-Installation**.

## Funktionen

- **Folder-basierter Datei-Browser:** links ein aufklappbarer Ordner-Baum der Festplatte
  (unter Windows werden alle Laufwerke als Wurzeln angezeigt, sonst `/` und das Home-Verzeichnis)
- **Dateiliste:** alle Audiodateien des gewählten Ordners in der Mitte, inkl. Tags
  (Titel, Interpret, Album, Sternebewertung, Dauer, Format/Bitrate), sortierbar per Klick auf die Spaltenköpfe
- **Album-Cover:** links unten wird das Cover des ausgewählten Albums angezeigt
- **Player-Leiste unten:** ⏮ Vorheriger, ▶/⏸ Play/Pause, ⏹ Stop, ⏭ Nächster, Fortschrittsbalken
  (klickbar zum Springen), Zeitanzeige (aktuell/gesamt), Lautstärke-Regler
- **Tags & Sternebewertungen (Popularimeter):** Anzeige der Bewertung als ★ in der Liste;
  Setzen/Entfernen per **Rechtsklick → „Sternebewertung setzen“**
  - MP3: ID3-`POPM`-Frame (Rating-Byte, 5 Sterne = 255)
  - FLAC/OGG: Vorbis-Comments `RATING` (0–100) und `FMPS_RATING` (0–5)
- **Flexibles Layout:** alle Bereiche über verschiebbare Trennlinien (PanedWindow) anpassbar;
  Fenstergröße, Sash-Positionen, **letzter Ordner**, Favoriten und Spalten werden gespeichert
  und beim nächsten Start wiederhergestellt
- **Favoriten:** beliebige Ordner links oben anpinnen („+ pin“ bzw. *Ansicht → … pinnen*),
  per Doppelklick direkt laden
- **Konfigurierbare Spalten:** über *Ansicht → Spalten anpassen …* Felder ein-/ausblenden,
  Reihenfolge per ▲/▼ ändern, Breite setzen — verfügbare Felder: Nr., Titel, Interpret, Album,
  Bewertung, Dauer, Bitrate, Genre, Jahr, Kommentar, Größe, Format, Datei, Pfad
- **Eigenschaften-Dialog:** Rechtsklick auf einen Titel → „Eigenschaften …“ — Reiter **Tags**
  (Titel, Interpret, Album, Albuminterpret, Komponist, Genre, Jahr, Track, Disc, Kommentar,
  Bewertung — alles editierbar), **Details** (Pfad, Größe, Bitrate, Samplerate, Kanäle, Dauer)
  und **Bewertungsfelder** (welche Rating-Felder in der Datei stehen)
- **Mehrfachauswahl:** mehrere Titel markieren (Klick, Strg+Klick, Shift+Klick) — Rechtsklick-Menü
  (Bewertung, Eigenschaften) wirkt auf **alle** markierten Dateien, z. B. Artist eines ganzen Albums ändern
- **Tastenkürzel:** Enter = Wiedergabe des markierten Titels starten, Leertaste = Play/Pause,
  → = nächster Titel, ← = vorheriger Titel
- **Spalten per Rechtsklick auf die Kopfzeile** ein-/ausblenden und per Drag verschieben
  (Reihenfolge wird gespeichert); Felder: Nr., Titel, Interpret, Album, Bewertung, Dauer, Bitrate,
  Genre, Jahr, Kommentar, Größe, Format, Datei, Pfad
- **Einstellungen (Preferences):** Farbschema **Hell/Dunkel** (Dark Mode), „letzten Ordner beim Start
  laden", Start-Lautstärke — alles in state.json gespeichert
- Rechtsklick auf einen Titel → **„Im Explorer/Finder öffnen"** (Windows: Explorer mit markierter
  Datei, macOS: Finder, Linux: Dateimanager)
- **Cover-Reiter** in den Eigenschaften: Cover anzeigen, ersetzen oder entfernen
- Automatischer Wechsel zum nächsten Titel am Track-Ende

## Bewertungsfelder (Rating)

Bewertungen werden in **allen bekannten Feldern** gelesen und geschrieben:

| Datei | Felder |
|---|---|
| MP3 (ID3) | `POPM` (POPULARIMETER — Traktor, MediaMonkey neu, Skala 0–255) und TXXX `RATING MM` (MediaMonkey alt, 0–100) |
| FLAC/OGG | `RATING` (MediaMonkey), `RATING WMP` (Traktor), `FMPS_RATING` |

Beim Lesen wird das erste gesetzte Feld verwendet (Skalen 0–5 / 0–100 / 0–255 werden automatisch
auf 0–5 Sterne normiert), beim Schreiben werden alle Felder des Formats beschrieben.

## Unterstützte Formate

Über SDL_mixer (in pygame enthalten): **MP3, FLAC, OGG/Vorbis, WAV, OPUS** (je nach System-Build).
FLAC und MP3 sind die priorisierten Formate und funktionieren überall.

Hinweis: M4A/AAC/WMA werden im Datei-Browser mit aufgeführt, können aber von SDL_mixer nicht
decodiert werden — beim Abspielen erscheint dann ein entsprechender Hinweis. Für diese Formate
wäre ein VLC-basierter Player nötig.

## Fertige Programmdateien (kein Python nötig)

Zum Starten wird **keine Python-Installation und keine PATH-Variable** gebraucht — es gibt
fertige Dateien pro System:

- **Windows:** `SePlayer.exe` — Doppelklick genügt. Beim ersten Start meldet sich evtl. der
  Windows-SmartScreen (App ist nicht signiert) → „Weitere Informationen" → „Trotzdem ausführen"
- **macOS:** `SePlayer.dmg` — DMG **einmalig** öffnen, `SePlayer.app` per Drag & Drop in den
  Programme-Ordner (Applications-Link liegt direkt im DMG), DMG auswerfen. Danach startet man
  SePlayer normal aus dem Programme-Ordner — die DMG wird nicht mehr gebraucht.
  Erster Start nach dem Download: Gatekeeper meldet sich einmalig → Rechtsklick auf die App →
  „Öffnen" (oder Systemeinstellungen → Sicherheit → „Trotzdem öffnen"). Ohne Apple-Developer-
  Signierung (kostenpflichtig) erscheint dieser eine Hinweis immer.
- **Linux:** `SePlayer-linux-x86_64` — `chmod +x SePlayer-linux-x86_64 && ./SePlayer-linux-x86_64`
  (braucht glibc, auf den meisten Distributionen vorhanden)

Die Binaries werden bei jedem Push automatisch per **GitHub Actions** gebaut (als Artefakte des
Workflow-Runs). Ein Tag `v...` (z. B. `git tag v1.0.0 && git push origin v1.0.0`) veröffentlicht
zusätzlich ein **Release** mit allen drei Dateien als Download.

## Entwicklung: Voraussetzungen & Start mit Python

- Python 3.10 oder neuer — auf dem Mac am besten von https://www.python.org/downloads/
  (diese Installation bringt tkinter und pip mit; das macOS-System-python3 hat teils kein tkinter)
- Ein Ausgabegerät (Soundkarte) — logisch notwendig zum Abspielen

```bash
pip3 install -r requirements.txt    # unter Windows meist: pip
python3 se_player.py                # unter Windows meist: python
```

### Mac: „zsh: command not found: pip / python"

macOS bringt `python` und `pip` nicht im PATH. Lösung mit `python3` und einem virtuellen Environment:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python se_player.py
```

Falls `python3` ebenfalls fehlt: Python 3 von python.org installieren und danach ein neues
Terminalfenster öffnen. Innerhalb des aktivierten venv funktionieren danach auch `python` und `pip`.

## Selbst bauen (auf dem jeweiligen System; Cross-Build geht nicht)

```bash
pip3 install -r requirements.txt -r requirements-build.txt
pyinstaller se_player.spec --noconfirm --clean
# Ergebnis in dist/:  SePlayer.exe (Windows) | SePlayer.app (macOS) | SePlayer (Linux)
# macOS .app -> .dmg:  hdiutil create -volname SePlayer -srcfolder dist/SePlayer.app -ov dist/SePlayer.dmg
```

## Bedienung

1. Links im Ordner-Baum einen Ordner aufklappen und anklicken (oder *Datei → Ordner öffnen …*)
2. In der Mitte per Doppelklick oder **Enter** einen Titel starten; mehrere Titel per Strg/Shift-Klick markieren
3. Unten über die Player-Leiste steuern; Fortschrittsbalken ziehen = Springen im Titel
4. Rechtsklick auf einen Titel → Sternebewertung (1–5 ★) setzen oder „Eigenschaften …“ zum
   Bearbeiten aller Tags; Bewertungen landen in allen bekannten Rating-Feldern (siehe oben)

## Projektstruktur

```
seplayer/  (Repo)
├── se_player.py                 # Startpunkt
├── se_player.spec               # PyInstaller-Spec (fertige Binaries: exe/app/linux)
├── requirements.txt             # Laufzeit-Abhängigkeiten (pygame, mutagen, Pillow)
├── requirements-build.txt       # Build-Abhängigkeiten (PyInstaller)
├── .github/workflows/build.yml  # automatischer Binary-Build (exe / dmg / linux)
├── README.md
└── seplayer/
    ├── __init__.py
    ├── audio.py                 # Wiedergabe-Engine (pygame.mixer)
    ├── tags.py                  # Tags lesen/schreiben, Rating-Felder (POPM, RATING MM, RATING, RATING WMP …), Cover
    ├── state.py                 # gemerkter Zustand (state.json: Fenster, letzter Ordner, Favoriten, Spalten, Theme)
    ├── theme.py                 # Farbschema Hell/Dunkel
    ├── preferences.py           # Einstellungen-Dialog
    ├── properties.py            # Eigenschaften-Dialog (Tags/Details/Bewertungsfelder/Cover, Mehrfachauswahl)
    ├── util.py                  # Format-Helfer
    └── gui.py                   # tkinter-Oberfläche (Favoriten, Baum, Cover, Liste, Player-Leiste)
```

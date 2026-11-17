# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für SePlayer.

Erzeugt eine einzelne startfähige Datei:
  Windows: dist/SePlayer.exe   (onefile, kein Konsolenfenster)
  macOS:   dist/SePlayer.app   (Bundle; per hdiutil als .dmg packbar)
  Linux:   dist/SePlayer       (onefile, ausführbar)
"""
import sys

a = Analysis(
    ["se_player.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "mutagen", "mutagen.mp3", "mutagen.flac", "mutagen.mp4",
        "mutagen.oggvorbis", "mutagen.oggopus", "mutagen.wave", "mutagen.aiff",
        "pygame.mixer",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SePlayer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="SePlayer.app",
        icon=None,
        bundle_identifier="com.thesepix.seplayer",
    )

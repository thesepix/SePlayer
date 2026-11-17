# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für Mp3Player.

Erzeugt eine einzelne startfähige Datei:
  Windows: dist/Mp3Player.exe   (onefile, kein Konsolenfenster)
  macOS:   dist/Mp3Player.app   (Bundle; per hdiutil als .dmg packbar)
  Linux:   dist/Mp3Player       (onefile, ausführbar)
"""
import sys

a = Analysis(
    ["mp3_player.py"],
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
    name="Mp3Player",
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
        name="Mp3Player.app",
        icon=None,
        bundle_identifier="com.thesepix.mp3player",
    )

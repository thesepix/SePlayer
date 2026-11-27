# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für SePlayer.

Erzeugt eine einzelne startfähige Datei:
  Windows: dist/SePlayer.exe   (onefile, kein Konsolenfenster)
  macOS:   dist/SePlayer.app   (Bundle; per hdiutil als .dmg packbar)
  Linux:   dist/SePlayer       (onefile, ausführbar)
"""
import os
import sys

a = Analysis(
    ["se_player.py"],
    pathex=[],
    binaries=[],
    datas=[(os.path.join("seplayer", "assets", "icon.png"), os.path.join("seplayer", "assets")),
           (os.path.join("seplayer", "assets", "icon_dark.png"), os.path.join("seplayer", "assets"))],
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
    icon=os.path.join("seplayer", "assets", "icon.ico"),
    disable_windowed_traceback=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="SePlayer.app",
        icon=os.path.join("seplayer", "assets", "icon.ico"),
        bundle_identifier="com.thesepix.seplayer",
    )

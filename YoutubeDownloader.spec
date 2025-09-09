# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

block_cipher = None

# Use the folder you run PyInstaller from
BASE = Path.cwd()

DATAS = [
    (str(BASE / "Graphics.ui"), "."),
    (str(BASE / "YouTube.ico"), "."),
]

BINARIES = [
    (str(BASE / "tools" / "ffmpeg" / "ffmpeg.exe"),  "tools/ffmpeg"),
    (str(BASE / "tools" / "ffmpeg" / "ffprobe.exe"), "tools/ffmpeg"),
]

HIDDEN = ["PyQt5", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.QtWidgets", "yt_dlp"]

a = Analysis(
    ["YoutubeDownloader.py"],
    pathex=[str(BASE)],
    binaries=BINARIES,
    datas=DATAS,
    hiddenimports=HIDDEN,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="YoutubeDownloader",
    icon=str(BASE / "YouTube.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                 # ok even if UPX is missing
    console=False,            # GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

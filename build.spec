# -*- mode: python ; coding: utf-8 -*-
"""Lean PyInstaller spec for VoiceToText Widget — only needed modules."""

block_cipher = None

# Only the hidden imports we actually need — no collect_submodules
hidden_imports = [
    # faster-whisper internals
    'faster_whisper',
    'faster_whisper.transcribe',
    'faster_whisper.audio',
    # ctranslate2
    'ctranslate2',
    'ctranslate2.runtime',
    # audio
    'sounddevice',
    '_sounddevice_data',
    # pynput
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._win32',
    'pynput.mouse',
    'pynput.mouse._win32',
    'pynput._util',
    'pynput._util.win32',
    # PyQt5 — only what we use
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    # others
    'pyperclip',
    'numpy',
    'numpy.core',
]

# Data files — keep minimal
datas = []

a = Analysis(
    ['launch.py'],
    pathex=[r'C:\Users\mikhail\.openclaw\workspace\voice-widget'],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Strip heavy unused packages
        'tensorflow', 'keras', 'tensorboard',
        'torch', 'torchvision', 'torchaudio',
        'matplotlib', 'tkinter',
        'PyQt5.QtWebEngine', 'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtQuickWidgets',
        'PyQt5.QtBluetooth', 'PyQt5.QtDesigner', 'PyQt5.QtHelp',
        'PyQt5.QtLocation', 'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtNetwork', 'PyQt5.QtNfc', 'PyQt5.QtOpenGL',
        'PyQt5.QtPositioning', 'PyQt5.QtPrintSupport',
        'PyQt5.QtQml', 'PyQt5.QtSensors', 'PyQt5.QtSerialPort',
        'PyQt5.QtSql', 'PyQt5.QtSvg', 'PyQt5.QtTest',
        'PyQt5.QtXml', 'PyQt5.QtXmlPatterns',
        'pandas', 'scipy', 'sklearn',
        'pyarrow', 'numba', 'llvmlite',
        'lxml', 'h5py', 'onnxruntime',
        'grpc', 'rich', 'anyio',
        'PIL', 'Pillow',
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VoiceToTextWidget',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=None,
)

# -*- mode: python ; coding: utf-8 -*-
"""Lean PyInstaller spec for VoiceToText Widget."""

import os
import glob

block_cipher = None

# Collect torch DLLs that ctranslate2 needs at runtime
torch_lib_dir = r'C:\Users\mikhail\AppData\Local\Programs\Python\Python313\Lib\site-packages\torch\lib'
torch_dlls = []
if os.path.isdir(torch_lib_dir):
    for dll in glob.glob(os.path.join(torch_lib_dir, '*.dll')):
        torch_dlls.append((dll, '.'))

# Also collect ctranslate2 native libs
ct2_dir = r'C:\Users\mikhail\AppData\Local\Programs\Python\Python313\Lib\site-packages\ctranslate2'
ct2_dlls = []
if os.path.isdir(ct2_dir):
    for dll in glob.glob(os.path.join(ct2_dir, '*.dll')):
        ct2_dlls.append((dll, '.'))

# Only the hidden imports we actually need
hidden_imports = [
    'faster_whisper',
    'faster_whisper.transcribe',
    'faster_whisper.audio',
    'ctranslate2',
    'sounddevice',
    'pynput',
    'pynput.keyboard',
    'pynput.keyboard._win32',
    'pynput.mouse',
    'pynput.mouse._win32',
    'pynput._util',
    'pynput._util.win32',
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'pyperclip',
    'numpy',
    'numpy.core',
    'av',
]

datas = []

a = Analysis(
    ['launch.py'],
    pathex=[r'C:\Users\mikhail\.openclaw\workspace\voice-widget'],
    binaries=torch_dlls + ct2_dlls,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tensorflow', 'keras', 'tensorboard',
        'matplotlib', 'tkinter',
        'PyQt5.QtWebEngine', 'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtQml', 'PyQt5.QtQuick', 'PyQt5.QtQuickWidgets',
        'PyQt5.QtBluetooth', 'PyQt5.QtDesigner', 'PyQt5.QtHelp',
        'PyQt5.QtLocation', 'PyQt5.QtMultimedia', 'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtNetwork', 'PyQt5.QtNfc', 'PyQt5.QtOpenGL',
        'PyQt5.QtPositioning', 'PyQt5.QtPrintSupport',
        'PyQt5.QtSensors', 'PyQt5.QtSerialPort',
        'PyQt5.QtSql', 'PyQt5.QtSvg', 'PyQt5.QtTest',
        'PyQt5.QtXml', 'PyQt5.QtXmlPatterns',
        'pandas', 'scipy', 'sklearn',
        'pyarrow', 'numba', 'llvmlite',
        'lxml', 'h5py', 'onnxruntime',
        'grpc', 'rich', 'anyio',
        'PIL', 'Pillow',
        'torch.distributed', 'torch.utils.tensorboard',
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

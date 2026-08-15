# -*- mode: python ; coding: utf-8 -*-
"""Lean PyInstaller spec for VoiceToText Widget."""

from PyInstaller.utils.hooks import collect_all, collect_data_files

block_cipher = None

# Pull in everything faster_whisper and ctranslate2 ship — native libs
# (ctranslate2.dll, libiomp5md.dll, cudnn64_9.dll) plus faster_whisper's bundled
# Silero VAD asset (assets/silero_vad_v6.onnx). collect_all keeps them inside
# their package directories, where the packages' own loaders expect to find them
# (do NOT flatten these to the bundle root — a duplicate libiomp5md.dll makes
# the OpenMP runtime initialize twice and segfault).
ct2_datas, ct2_binaries, ct2_hidden = collect_all('ctranslate2')
fw_datas, fw_binaries, fw_hidden = collect_all('faster_whisper')

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
    # onnxruntime is imported lazily (try/except) by faster_whisper.vad for the
    # Silero VAD filter, so PyInstaller drops it as "optional". Force-include it
    # so the bundled hook-onnxruntime collects its native libs.
    'onnxruntime',
] + ct2_hidden + fw_hidden

datas = ct2_datas + fw_datas

a = Analysis(
    ['launch.py'],
    pathex=[r'C:\Users\mikhail\.openclaw\workspace\voice-widget'],
    binaries=ct2_binaries + fw_binaries,
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
        'lxml', 'h5py',
        'grpc', 'rich', 'anyio',
        'PIL', 'Pillow',
        'torch', 'torch.distributed', 'torch.utils.tensorboard',
    ],
    cipher=block_cipher,
)

# Drop the MSVC runtime DLLs that PyQt5 bundles under Qt5/bin. They are a
# different version from the canonical copies PyInstaller places at the bundle
# root (the ones ctranslate2 / numpy link against), and because Qt5/bin is on
# the DLL search path, ctranslate2 would otherwise load Qt's MSVCP140.dll and
# crash with an access violation (0xC0000005) the first time it calls into the
# C++ runtime — e.g. while constructing the Whisper model. With the duplicates
# gone, every module resolves the single, ABI-consistent MSVCP140.dll at root.
_DROP_RUNTIMES = {'msvcp140.dll', 'msvcr140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'concrt140.dll'}
a.binaries = [
    b for b in a.binaries
    if not (
        '/qt5/bin/' in b[0].replace('\\', '/').lower()
        and b[0].replace('\\', '/').split('/')[-1].lower() in _DROP_RUNTIMES
    )
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VoiceToTextWidget',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # no console window; logs go to voicetotext.log (launch.py)
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VoiceToTextWidget',
)

"""Entry point for PyInstaller builds.

Imports from src package and runs main().
"""
import sys
import os

# Print a Python traceback on native crashes (segfault) so failures during
# native-lib init (ctranslate2/onnxruntime) are diagnosable in frozen builds.
try:
    import faulthandler
    faulthandler.enable()
except Exception:
    pass

# Ensure src is importable when frozen
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    base = os.path.dirname(sys.executable)
    sys.path.insert(0, base)
else:
    base = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base)

# --- Native-lib load ordering ----------------------------------------------
# This app does not use torch (faster-whisper runs on ctranslate2 + onnxruntime),
# and ctranslate2.specs imports it only optionally. Pre-empt it so that an
# optional `import torch` (e.g. a broken install left on the machine) cannot
# crash startup. Harmless in the frozen build, where torch is excluded anyway.
sys.modules["torch"] = None

# Import ctranslate2 (used by faster-whisper) before PyQt5 is pulled in. This
# loads its Intel OpenMP runtime (libiomp5md.dll) early, which keeps model
# construction stable when Qt is active. (The frozen build additionally needs
# the MSVC-runtime dedup in build.spec — see the _DROP_RUNTIMES block there.)
try:
    import ctranslate2  # noqa: F401  (side effect: load libiomp5md.dll early)
except Exception:
    pass

from src.main import main

if __name__ == "__main__":
    main()

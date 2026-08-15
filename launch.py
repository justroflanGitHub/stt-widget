"""Entry point for PyInstaller builds.

Imports from src package and runs main().
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _setup_logging() -> None:
    """Route logs to a file next to the app — the frozen build has no console.

    Source (dev) runs keep the usual terminal output instead, so no log file
    litters the working tree.
    """
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if getattr(sys, "frozen", False):
        log_path = Path(sys.executable).resolve().parent / "voicetotext.log"
        try:
            handler = RotatingFileHandler(
                log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
            )
            handler.setFormatter(fmt)
            root.addHandler(handler)

            # Native-crash tracebacks must go to the file too: in a console-less
            # build sys.stderr is a null sink, so faulthandler needs a target.
            try:
                import faulthandler
                faulthandler.enable(file=handler.stream)
            except Exception:
                pass
            return
        except Exception:
            pass  # e.g. read-only install dir — run silent rather than crash

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        import faulthandler
        faulthandler.enable()
    except Exception:
        pass


_setup_logging()

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

# Import ctranslate2 (used by faster_whisper) before PyQt5 is pulled in. This
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

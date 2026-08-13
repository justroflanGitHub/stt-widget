"""Entry point for PyInstaller builds.

Imports from src package and runs main().
"""
import sys
import os

# Ensure src is importable when frozen
if getattr(sys, "frozen", False):
    # Running as PyInstaller bundle
    base = os.path.dirname(sys.executable)
    sys.path.insert(0, base)
else:
    base = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, base)

from src.main import main

if __name__ == "__main__":
    main()

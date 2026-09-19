"""Build-time shim: pre-import onnxruntime in PyInstaller's isolated child.

PyInstaller's dependency-analysis child imports collected packages one by one
in a single process. With PyQt5 imported first, Qt5Core breaks onnxruntime
DLL initialization (WinError 1114, or a hard 0xC0000005 on newer ORT) and the
child dies mid-build. Importing onnxruntime first keeps the child alive —
the same load order launch.py enforces in the frozen app via
`import ctranslate2` before PyQt5. sitecustomize runs at interpreter startup,
before any PyInstaller child call, so this restores a survivable order.

Only used when building (PYTHONPATH=build_shim); never ships in the bundle.
"""
try:
    import onnxruntime  # noqa: F401
except Exception:
    pass

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] — 2026-09-20

### Fixed
- **The widget could hang in Processing forever on CUDA.** ctranslate2.dll loads `cublas64_12.dll` lazily at the first GPU matmul; when that DLL is missing (the default on machines without a CUDA 12 runtime on the DLL search path) the model still "loads" into VRAM, but the first real inference deadlocks inside ctranslate2 instead of raising. The transcription worker never returned and the widget stayed yellow indefinitely.
- cuBLAS now ships with the app: `build.spec` bundles `cublas64_12.dll` + `cublasLt64_12.dll` from the `nvidia-cublas-cu12` wheel (CUDA 12.4, matching the CTranslate2 4.8.x build; new entry in `requirements.txt`), so GPU inference works out of the box.

### Added
- **CUDA warm-up probe**: after loading the model on GPU, a tiny real inference forces the lazy CUDA library loads *before* the model is reported ready. An exception — or a deadlock, caught by running the probe in a disposable daemon thread with `CUDA_WARMUP_TIMEOUT_S` — falls back to CPU, so a broken CUDA stack can never freeze a real recording.
- `cuda_available()` additionally verifies `cublas64_12.dll` is loadable (by name, or from a pip-installed `nvidia-cublas-cu12` via absolute-path preload, which ctranslate2's later by-name load reuses), so `auto` no longer resolves to a GPU that would deadlock at first use.
- **Transcription watchdog** (`TRANSCRIBE_TIMEOUT_S`, 120 s): a worker stuck in a native call no longer strands the UI — the tray reports a timeout and the model reloads on CPU; a late result from the abandoned worker is discarded instead of flashing a bogus Done state.
- Build shim (`build_shim/sitecustomize.py`, enabled via `PYTHONPATH` when building): pre-imports onnxruntime in PyInstaller's isolated analysis child, whose PyQt5-first import order otherwise breaks onnxruntime DLL initialization and crashes the build.
- 3 new tests (68 total): missing cuBLAS forces `auto` → CPU; warm-up exception and warm-up deadlock both fall back to CPU.

### Changed
- `onnxruntime` pinned to 1.26.0 (newer releases crash when imported after PyQt5 in the same process).

## [1.2.0] — 2026-09-19

### Added
- **CUDA GPU support**: the Whisper model can now load into VRAM via CTranslate2 (`float16` compute) instead of CPU `int8`. New **Device** tray menu — `Auto (GPU if available)` / `CPU` / `GPU (CUDA)` — and a `device` key in `settings.json` (default `auto`).
- Auto-detection: `auto` resolves through `ctranslate2.get_cuda_device_count()`; an explicit CUDA pick that fails at runtime (missing driver/cuDNN) retries once on CPU, and the tray reports what actually loaded ("Ready on GPU (CUDA)" / "CUDA unavailable — running on CPU").
- `Transcriber.effective_device` property exposing the concrete device after resolution/fallback.
- 9 new tests: device resolution (`auto`/`cpu`/`cuda`), compute-type pairing (`float16` vs `int8`), CUDA→CPU fallback, settings validation for `device` (65 total).

### Changed
- Compute type is now derived from the resolved device (single mapping in `constants.compute_type_for_device`) instead of a hardcoded `int8`.
- `Transcriber.__init__` signature: `compute_type` is optional and defaults to the device-appropriate value.

## [1.1.0] — 2026-09-01

### Added
- Activation via the **right Ctrl** — the new default global hotkey. The hotkey engine distinguishes physical key sides, so Left Ctrl keeps its normal behaviour (copy/paste, IDE shortcuts).
- Side-aware hotkey engine (`src/hotkey.py`): pynput's `GlobalHotKeys` collapses `ctrl_l`/`ctrl_r` onto one generic key and cannot fire a Right-Ctrl-only hotkey; the new listener built on pynput's raw hook keeps the distinction. Generic `<ctrl>` in combination strings still matches both sides, preserving older `settings.json` files.
- Hotkey dialog accepts a lone side modifier (Right Ctrl, Left Ctrl, Right Alt…) as a complete single-key hotkey, and captures the physical side of modifiers inside combinations via native scan codes.
- 24 new tests for the hotkey engine and dialog formatting (56 total). Verified against real OS-level key events (injected via `SendInput`) and end-to-end with the full app stack.

### Changed
- `settings.json` `global_hotkey` default is now `"<ctrl_r>"` (was `"<ctrl>+<alt>+v"`).
- Existing hotkey log line added on activation for file-log diagnostics.

## [1.0.0] — 2026-08-12

### Added
- Initial release of VoiceToText Widget.
- Frameless always-on-top PyQt5 widget (64×64px, draggable).
- Two interaction modes: Toggle and Push-to-Talk.
- Visual states: idle (blue mic), recording (pulsing red), processing (spinner), done (green flash), loading (pulsing dots).
- Speech-to-Text via `faster-whisper` with `int8` CPU compute, auto ru/en detection.
- Auto-copy recognized text to clipboard via `pyperclip`.
- System tray icon with context menu (Mode, Language, Quit).
- Global hotkey `Ctrl+Alt+V` via `pynput`.
- Settings persistence to `settings.json` (mode, language, model_size, widget_position, global_hotkey).
- All icons drawn programmatically with QPainter — no external assets.
- Background model loading with loading indicator.
- Threaded audio recording and transcription (non-blocking UI).
- 32 unit tests (config, transcriber, audio recorder) — all pass without microphone or model download.

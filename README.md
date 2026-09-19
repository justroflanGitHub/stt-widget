# VoiceToText Widget

A small always-on-top floating widget for Windows that records your voice and transcribes it to text using `faster-whisper`. Recognized text is automatically copied to the clipboard.

![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **Floating always-on-top widget** — 72×72px, draggable, frameless, with a hand-drawn mic icon (no external assets).
- **Two interaction modes:**
  - **Toggle** — click once to start, click again to stop.
  - **Push-to-Talk** — click and hold to record, release to transcribe.
- **Visual feedback:**
  - 🔵 Idle — blue mic icon
  - 🔴 Recording — pulsing red circle
  - 🟡 Processing — spinning arc + dots
  - 🟢 Done — green checkmark flash + tooltip with recognized text
  - 🩷 Loading — pulsing dots while model loads
- **Speech-to-Text** via `faster-whisper` (CTranslate2 backend).
  - **CPU (`int8`) or GPU (`float16` on CUDA)** — device `auto` by default: the app detects the GPU and loads the model into VRAM; falls back to CPU when CUDA is unavailable or the CUDA load fails.
  - Auto language detection (ru/en) or force a language.
  - Model `small` by default (configurable).
- **Auto-copy** recognized text to clipboard.
- **System tray** with right-click menu: hotkey, Mode, Language, Model, Device, Quit.
- **Global hotkey** — **Right Ctrl** by default (configurable).
- **Settings** persisted to `settings.json`.

## Hotkey

The default activation key is the **right Ctrl only** — pressing it starts recording, pressing it again stops and transcribes. The left/right distinction is real, not cosmetic: **Left Ctrl keeps working normally** (copy/paste, IDE shortcuts, etc.).

Under the hood, `pynput`'s built-in `GlobalHotKeys` collapses `ctrl_l`/`ctrl_r` onto a single generic key, so a Right-Ctrl-only hotkey is impossible with it. This app ships its own side-aware listener (`src/hotkey.py`) built on pynput's raw keyboard hook:

- `<ctrl_r>` matches **only** the physical right Ctrl (same for `<ctrl_l>`, `<alt_r>`, `<shift_r>`, `<cmd_r>`…);
- generic `<ctrl>` in a combination string still matches both sides, so old `settings.json` values like `<ctrl>+<alt>+v` keep working;
- a held key is not re-triggered by OS auto-repeat.

Change the key from the tray menu — **Set Hotkey…** opens a dialog where you press the new combination; a lone Right Ctrl (or Left Ctrl / Right Alt, etc.) is accepted as a complete single-key hotkey.

## Installation

```powershell
# Clone
git clone <repo-url>
cd voice-widget

# Install dependencies
py -m pip install -r requirements.txt

# Run
py -m src.main
```

### Requirements

- **Python 3.13** (use `py` launcher on Windows)
- **Windows 10/11** (tested on Windows 10 x64)
- Working microphone
- ~1GB RAM (with the `small` model)

## Usage

1. Launch the app — a small widget appears. Wait for the model to load (pink dots).
2. **Right Ctrl** anywhere — start recording; press again — stop and transcribe. Or click the widget (Toggle mode) / hold it (Push-to-Talk mode).
3. Recognized text is automatically copied to your clipboard.
4. Right-click the system tray icon to change the hotkey, mode, language, or model — or quit.

## Installation

```powershell
# Clone
git clone <repo-url>
cd voice-widget

# Install dependencies
py -m pip install -r requirements.txt

# Run
py -m src.main
```

### Requirements

- **Python 3.13** (use `py` launcher on Windows)
- **Windows 10/11** (tested on Windows 10 x64)
- Working microphone
- ~500MB RAM (with `base` model)

## Usage

1. Launch the app — a small widget appears. Wait for the model to load (pink dots).
2. **Toggle mode:** Click the widget to start recording. Click again to stop.
3. **Push-to-Talk mode:** Hold the widget to record. Release to transcribe.
4. **Global hotkey:** `Ctrl+Alt+V` toggles recording from any app.
5. Recognized text is automatically copied to your clipboard.
6. Right-click the system tray icon to change mode/language or quit.

### Settings (`settings.json`)

| Key               | Type    | Default              | Description                          |
|-------------------|---------|----------------------|--------------------------------------|
| `mode`            | string  | `"toggle"`           | `"toggle"` or `"push_to_talk"`       |
| `language`        | string  | `"auto"`             | `"auto"`, `"ru"`, or `"en"`          |
| `model_size`      | string  | `"small"`            | faster-whisper model size            |
| `device`          | string  | `"auto"`             | `"auto"`, `"cpu"`, or `"cuda"`        |
| `widget_position` | array   | `[100, 100]`         | `[x, y]` screen coordinates           |
| `global_hotkey`   | string  | `"<ctrl_r>"`         | side-aware pynput format (see Hotkey) |

## Architecture

```
voice-widget/
├── src/
│   ├── __init__.py          # Package metadata
│   ├── constants.py         # All magic numbers & strings (single source of truth)
│   ├── config.py            # Settings load/save (JSON)
│   ├── widget.py            # PyQt5 frameless widget + QPainter icons
│   ├── audio_recorder.py    # sounddevice capture (thread-safe)
│   ├── transcriber.py       # faster-whisper wrapper (background model load)
│   ├── hotkey.py            # side-aware global hotkey listener (R-Ctrl ≠ L-Ctrl)
│   ├── hotkey_dialog.py     # capture-a-hotkey dialog (distinguishes key sides)
│   ├── clipboard_util.py    # pyperclip wrapper
│   ├── tray.py              # QSystemTrayIcon + context menu
│   └── main.py              # AppController wiring everything together
├── tests/
│   ├── conftest.py          # Path setup
│   ├── test_config.py       # Settings tests (8 tests)
│   ├── test_transcriber.py  # Transcriber tests (7 tests)
│   ├── test_audio.py        # Audio recorder tests (12 tests)
│   └── test_hotkey.py       # Side-aware hotkey engine tests (24 tests)
├── build.spec               # PyInstaller build (onedir)
├── launch.py                # Entry point (dev + frozen builds)
├── settings.json
├── requirements.txt
├── CHANGELOG.md
└── README.md
```

### Design Principles

1. **Single source of truth** — all constants in `constants.py`, no magic numbers.
2. **No duplicate functions** — shared logic lives in one place.
3. **Thread safety** — audio recording and model loading run on background threads. UI never blocks.
4. **Testability** — heavy modules (sounddevice, faster_whisper) imported lazily, mocked in tests.
5. **No external assets** — all icons drawn with QPainter at runtime.

### Threading Model

```
Main Thread (Qt event loop)
  ├── Widget UI updates
  ├── Tray interactions
  └── QTimer callbacks
        │
        ├── Model Loader Thread (daemon)
        │     └── WhisperModel(model_size, cpu|cuda, int8|float16)
        │           └── on CUDA failure → retry once on CPU
        │
        └── Transcribe Worker Thread (daemon, per-utterance)
              ├── AudioRecorder.stop() → np.ndarray
              ├── Transcriber.transcribe(audio)
              └── copy_to_clipboard(text)
                   └── QTimer.singleShot → UI update
```

## Testing

```powershell
py -m pytest tests/ -v
```

All 65 tests pass without a microphone or model download.

## Building

```powershell
py -m PyInstaller build.spec --noconfirm
```

Produces `dist/VoiceToTextWidget/` — a self-contained folder with `VoiceToTextWidget.exe`. Settings and logs are stored next to the executable.

## License

MIT

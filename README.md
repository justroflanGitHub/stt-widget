# VoiceToText Widget

A small always-on-top floating widget for Windows that records your voice and transcribes it to text using `faster-whisper`. Recognized text is automatically copied to the clipboard.

![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![PyQt5](https://img.shields.io/badge/PyQt5-5.15-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## Features

- **Floating always-on-top widget** — 64×64px, draggable, frameless, with a hand-drawn mic icon (no external assets).
- **Two interaction modes:**
  - **Toggle** — click once to start, click again to stop.
  - **Push-to-Talk** — click and hold to record, release to transcribe.
- **Visual feedback:**
  - 🔵 Idle — blue mic icon
  - 🔴 Recording — pulsing red circle
  - 🟡 Processing — spinning arc + dots
  - 🟢 Done — green checkmark flash + tooltip with recognized text
  - 🩷 Loading — pulsing dots while model loads
- **Speech-to-Text** via `faster-whisper` (CTranslate2 backend, CPU `int8` compute).
  - Auto language detection (ru/en) or force a language.
  - Model `base` by default (configurable).
- **Auto-copy** recognized text to clipboard.
- **System tray** with right-click menu: Mode, Language, Quit.
- **Global hotkey** — `Ctrl+Alt+V` (configurable).
- **Settings** persisted to `settings.json`.

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
| `model_size`      | string  | `"base"`             | faster-whisper model size            |
| `widget_position` | array   | `[100, 100]`         | `[x, y]` screen coordinates           |
| `global_hotkey`   | string  | `"<ctrl>+<alt>+v"`   | pynput hotkey format                  |

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
│   ├── clipboard_util.py    # pyperclip wrapper
│   ├── tray.py              # QSystemTrayIcon + context menu
│   └── main.py              # AppController wiring everything together
├── tests/
│   ├── conftest.py          # Path setup
│   ├── test_config.py       # Settings tests (8 tests)
│   ├── test_transcriber.py  # Transcriber tests (7 tests)
│   └── test_audio.py        # Audio recorder tests (12 tests)
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
        │     └── WhisperModel(model_size, cpu, int8)
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

All 32 tests pass without a microphone or model download.

## License

MIT

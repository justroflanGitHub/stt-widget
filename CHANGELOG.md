# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

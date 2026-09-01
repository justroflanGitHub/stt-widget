"""Tests for the side-aware hotkey engine (src/hotkey.py)."""

import pytest
from pynput.keyboard import Key, KeyCode

from src.hotkey import GlobalHotkeyListener, HotkeyMatcher, parse_combo
from src.hotkey_dialog import pretty_hotkey


class Recorder:
    """Callback target counting activations."""

    def __init__(self) -> None:
        self.fired = 0

    def __call__(self) -> None:
        self.fired += 1


# ── parse_combo ───────────────────────────────────────────────────────────────


def test_parse_side_specific_modifier():
    assert parse_combo("<ctrl_r>") == [frozenset({"ctrl_r"})]


def test_parse_generic_modifier_matches_both_sides():
    parts = parse_combo("<ctrl>")
    assert parts == [frozenset({"ctrl", "ctrl_l", "ctrl_r"})]


def test_parse_mixed_combo():
    parts = parse_combo("<ctrl>+<alt>+v")
    assert parts == [
        frozenset({"ctrl", "ctrl_l", "ctrl_r"}),
        frozenset({"alt", "alt_l", "alt_r"}),
        frozenset({"v"}),
    ]


@pytest.mark.parametrize("combo", ["", "<bogus>", "v+", "ctrl_r"])
def test_parse_invalid_raises(combo):
    with pytest.raises(ValueError):
        parse_combo(combo)


def test_parse_plus_character_is_a_valid_key():
    # A lone "+" parses as the plus key itself (pynput semantics), not garbage.
    assert parse_combo("+") == [frozenset({"+"})]


# ── HotkeyMatcher: Right Ctrl alone ───────────────────────────────────────────


def test_right_ctrl_fires_left_ctrl_does_not():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>": rec})

    m.press(Key.ctrl_l)
    assert rec.fired == 0

    m.press(Key.ctrl_r)
    assert rec.fired == 1


def test_generic_ctrl_events_also_trigger_side_combo():
    # Some input sources report the generic VK; it stands for the right key
    # only when the side combo was registered as side-specific — a generic
    # event must NOT satisfy a side-specific combo.
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>": rec})
    m.press(Key.ctrl)
    assert rec.fired == 0


def test_no_refire_on_held_key():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>": rec})

    m.press(Key.ctrl_r)
    m.press(Key.ctrl_r)  # OS auto-repeat
    m.press(Key.ctrl_r)
    assert rec.fired == 1


def test_refires_after_release():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>": rec})

    m.press(Key.ctrl_r)
    m.release(Key.ctrl_r)
    m.press(Key.ctrl_r)
    assert rec.fired == 2


def test_unrelated_key_press_does_not_refire():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>": rec})

    m.press(Key.ctrl_r)   # fires
    m.press(KeyCode.from_char("x"))  # not part of the combo
    assert rec.fired == 1


# ── HotkeyMatcher: combinations ───────────────────────────────────────────────


def test_legacy_default_combo_still_works():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl>+<alt>+v": rec})

    m.press(Key.ctrl_l)
    m.press(Key.alt_l)
    m.press(KeyCode.from_char("v"))
    assert rec.fired == 1

    m.release(Key.alt_l)
    m.release(Key.ctrl_l)
    m.release(KeyCode.from_char("v"))
    m.press(Key.ctrl_l)
    m.press(Key.alt_l)
    m.press(KeyCode.from_char("v"))
    assert rec.fired == 2


def test_legacy_combo_right_side_also_matches():
    # Generic modifiers in old settings must keep matching either side.
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl>+<alt>+v": rec})

    m.press(Key.ctrl_r)
    m.press(Key.alt_r)
    m.press(KeyCode.from_char("V"))  # upper-case variant of the same key
    assert rec.fired == 1


def test_side_combo_requires_that_side():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>+v": rec})

    m.press(Key.ctrl_l)
    m.press(KeyCode.from_char("v"))
    assert rec.fired == 0

    m.release(Key.ctrl_l)
    m.release(KeyCode.from_char("v"))
    m.press(Key.ctrl_r)
    m.press(KeyCode.from_char("v"))
    assert rec.fired == 1


def test_wrong_letter_does_not_complete_combo():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>+v": rec})

    m.press(Key.ctrl_r)
    m.press(KeyCode.from_char("x"))
    assert rec.fired == 0


def test_callback_exception_does_not_kill_matcher():
    m = HotkeyMatcher({"<ctrl_r>": lambda: 1 / 0})
    m.press(Key.ctrl_r)  # must not raise
    m.release(Key.ctrl_r)
    m.press(Key.ctrl_r)  # and keep working


def test_unknown_key_ignored():
    rec = Recorder()
    m = HotkeyMatcher({"<ctrl_r>": rec})
    m.press(None)
    m.release(None)
    assert rec.fired == 0


# ── GlobalHotkeyListener wiring (no listener thread started) ──────────────────


def test_listener_delivers_events_to_matcher():
    rec = Recorder()
    listener = GlobalHotkeyListener({"<ctrl_r>": rec})

    # Real (non-injected) hardware events reach the matcher…
    listener._on_press(Key.ctrl_l, injected=False)
    listener._on_press(Key.ctrl_r, injected=False)
    assert rec.fired == 1

    listener._on_release(Key.ctrl_r, injected=False)
    listener._on_press(Key.ctrl_r, injected=False)
    assert rec.fired == 2


def test_listener_ignores_injected_events_by_default():
    rec = Recorder()
    listener = GlobalHotkeyListener({"<ctrl_r>": rec})

    listener._on_press(Key.ctrl_r, injected=True)
    assert rec.fired == 0

    listener._on_press(Key.ctrl_r, injected=False)
    assert rec.fired == 1


# ── pretty_hotkey ─────────────────────────────────────────────────────────────


def test_pretty_default_hotkey():
    from src import constants as C

    assert pretty_hotkey(C.DEFAULT_HOTKEY) == "R-Ctrl"


def test_pretty_side_combo_sorted():
    assert pretty_hotkey("<ctrl_r>+v") == "R-Ctrl + V"


def test_pretty_legacy_combo():
    assert pretty_hotkey("<ctrl>+<alt>+v") == "Ctrl + Alt + V"

"""
hotkey.py — side-aware global hotkey listening.

``pynput.keyboard.GlobalHotKeys`` cannot tell the left and right variants of a
modifier key apart: its ``canonical()`` maps ``ctrl_l``/``ctrl_r`` (and the
alt/shift/win pairs) onto the generic key, so a hotkey registered as
``"<ctrl_r>"`` would never fire. This module reimplements the matching on top
of pynput's raw ``keyboard.Listener`` while keeping the distinction:

* side-specific names (``"<ctrl_r>"``) match only that physical key;
* generic modifiers (``"<ctrl>"``) keep matching both sides, so combination
  strings from older settings files keep working.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, FrozenSet, List, Optional, Tuple

from pynput import keyboard

logger = logging.getLogger(__name__)

#: Generic modifier name → every physical variant it should match. The first
#: entry is the generic key itself, which some input sources report instead of
#: a concrete side.
_MODIFIER_VARIANTS: Dict[str, Tuple[str, ...]] = {
    "ctrl": ("ctrl", "ctrl_l", "ctrl_r"),
    "alt": ("alt", "alt_l", "alt_r"),
    "shift": ("shift", "shift_l", "shift_r"),
    "cmd": ("cmd", "cmd_l", "cmd_r"),
}

#: Side-variant names, flattened — ``HotKey.parse`` hands side-specific
#: modifiers to us as bare virtual-key codes, and these are the names those
#: codes must resolve back to.
_SIDE_NAMES: Tuple[str, ...] = (
    "ctrl_l", "ctrl_r", "alt_l", "alt_r", "shift_l", "shift_r", "cmd_l", "cmd_r",
)


def _key_identity(key) -> Optional[str]:
    """Map a pynput key event onto a stable identity string.

    ``Key`` instances map onto their enum name (``"ctrl_r"``, ``"enter"``…).
    ``KeyCode`` instances map onto their lower-case character, or onto the
    modifier name their virtual key stands for — ``HotKey.parse`` turns
    ``"<ctrl_r>"`` into a bare ``KeyCode.from_vk(...)``, which must resolve to
    the same identity as the physical ``Key.ctrl_r`` press events. Anything
    unrecognised yields ``None`` and is ignored by the matcher.
    """
    if isinstance(key, keyboard.Key):
        return key.name
    if isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        if key.vk is not None:
            for name in _SIDE_NAMES:
                side_key = getattr(keyboard.Key, name, None)
                if side_key is not None and side_key.value.vk == key.vk:
                    return name
            return "vk:%d" % key.vk
    return None


def parse_combo(combo: str) -> List[FrozenSet[str]]:
    """Parse a pynput-style combination string into per-key identity sets.

    Each key of the combination becomes a set of identities that satisfies it:
    a generic modifier yields every side variant, everything else a single
    identity. The combination is complete while every set intersects the set of
    currently pressed keys.

    Raises:
        ValueError: if the string is malformed or names an unknown key.
    """
    parts = keyboard.HotKey.parse(combo)
    if not parts:
        raise ValueError("Empty hotkey combination")

    result: List[FrozenSet[str]] = []
    for part in parts:
        identity = _key_identity(part)
        if identity is None:
            raise ValueError("Unsupported key in combination %r" % combo)
        variants = _MODIFIER_VARIANTS.get(identity)
        result.append(frozenset(variants if variants else (identity,)))
    return result


class HotkeyMatcher:
    """Track pressed keys and fire callbacks when a combination completes.

    Pure state machine — no threads — so it is unit-testable with synthetic
    key objects.

    Args:
        hotkeys: mapping from combination string to callback, in the same
            format ``GlobalHotKeys`` accepts.

    Raises:
        ValueError: if any combination string is invalid.
    """

    def __init__(self, hotkeys: Dict[str, Callable[[], None]]) -> None:
        self._combos: List[Tuple[List[FrozenSet[str]], Callable[[], None]]] = []
        self._pressed: set = set()
        for combo, callback in hotkeys.items():
            self._combos.append((parse_combo(combo), callback))

    def press(self, key) -> None:
        """Feed a key-press event (called on the listener thread)."""
        identity = _key_identity(key)
        if identity is None or identity in self._pressed:
            # Unknown key, or OS auto-repeat of a held key — never re-trigger.
            return
        self._pressed.add(identity)
        for parts, callback in self._combos:
            if identity not in frozenset().union(*parts):
                # Only the completing press fires the combo; holding one key
                # and tapping another must not re-trigger it.
                continue
            if all(any(p in self._pressed for p in part) for part in parts):
                try:
                    callback()
                except Exception:
                    logger.exception("Hotkey callback for %s failed", callback)

    def release(self, key) -> None:
        """Feed a key-release event (called on the listener thread)."""
        identity = _key_identity(key)
        if identity is not None:
            self._pressed.discard(identity)


class GlobalHotkeyListener(keyboard.Listener):
    """pynput listener driving a :class:`HotkeyMatcher`.

    Drop-in replacement for ``keyboard.GlobalHotKeys`` that, unlike it,
    distinguishes the left and right physical variants of the modifier keys.

    Args:
        hotkeys: mapping from combination string to callback, as accepted by
            ``GlobalHotKeys``.
        ignore_injected: ignore ``SendInput``-injected key events (automation
            tools, on-screen keyboards). Tests that synthesize OS input pass
            ``False``.
    """

    def __init__(
        self,
        hotkeys: Dict[str, Callable[[], None]],
        ignore_injected: bool = True,
        **kwargs,
    ) -> None:
        self._matcher = HotkeyMatcher(hotkeys)
        self._ignore_injected = ignore_injected
        super().__init__(on_press=self._on_press, on_release=self._on_release, **kwargs)

    def _on_press(self, key, injected: bool = False) -> None:
        if injected and self._ignore_injected:
            return
        self._matcher.press(key)

    def _on_release(self, key, injected: bool = False) -> None:
        if injected and self._ignore_injected:
            return
        self._matcher.release(key)

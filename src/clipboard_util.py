"""
clipboard_util.py — Clipboard utilities built on top of pyperclip.

Single responsibility: put text on the clipboard and provide feedback.
"""

from __future__ import annotations

import logging
from typing import Optional

import pyperclip

logger = logging.getLogger(__name__)


def copy_to_clipboard(text: str) -> bool:
    """Copy *text* to the system clipboard.

    Args:
        text: The text to place on the clipboard.

    Returns:
        True on success, False on failure.
    """
    if not text:
        logger.warning("Attempted to copy empty text to clipboard.")
        return False

    try:
        pyperclip.copy(text)
        logger.info("Copied %d chars to clipboard.", len(text))
        return True
    except pyperclip.PyperclipException as exc:
        logger.error("Clipboard error: %s", exc)
        return False


def get_clipboard() -> Optional[str]:
    """Return current clipboard contents or ``None`` on failure."""
    try:
        return pyperclip.paste()
    except pyperclip.PyperclipException as exc:
        logger.error("Clipboard read error: %s", exc)
        return None

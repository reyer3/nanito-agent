"""Notification dispatcher — sends wish digests and status updates.

Tries WhatsApp first (via voice module's WhatsAppNotifier),
falls back to terminal/voice.
"""

from __future__ import annotations

from nanito_agent.inbox import Wish
from nanito_agent.voice import NanitoVoice


def _get_voice() -> NanitoVoice:
    """Lazy-init voice with auto-detection."""
    return NanitoVoice.auto_detect()


def notify_digest(wish: Wish) -> bool:
    """Send wish digest to user. Tries all available channels."""
    if not wish.digest:
        return False
    message = f"[nanito] Wish {wish.id[:8]}:\n{wish.digest}"
    voice = _get_voice()
    voice.announce(message)
    return True


def notify_completion(wish: Wish) -> bool:
    """Notify user that a wish was completed."""
    message = f"[nanito] Done: {wish.raw[:80]}"
    voice = _get_voice()
    voice.announce(message)
    return True


def notify_failure(wish: Wish, error: str) -> bool:
    """Notify user that a wish failed."""
    message = f"[nanito] Failed: {wish.raw[:60]} — {error[:80]}"
    voice = _get_voice()
    voice.announce(message)
    return True

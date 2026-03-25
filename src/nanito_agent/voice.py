"""Voice module — TTS, STT, and notification abstractions.

All providers handle "not installed" gracefully. Zero audio tools installed
means nanito falls back to text-only notifications. No external dependencies
are required in pyproject.toml — users install vosk/piper/elevenlabs themselves.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# TTS providers
# ---------------------------------------------------------------------------

@runtime_checkable
class TTSProvider(Protocol):
    def speak(self, text: str) -> Path | None: ...


class EspeakTTS:
    """Local TTS via espeak. Zero Python dependencies."""

    def __init__(self, lang: str = "es") -> None:
        self.lang = lang
        self._bin = shutil.which("espeak")

    def speak(self, text: str) -> Path | None:
        if not self._bin:
            return None
        out = Path(tempfile.mktemp(suffix=".wav", prefix="nanito_tts_"))
        try:
            subprocess.run(
                [self._bin, "-v", self.lang, "-w", str(out), text],
                capture_output=True,
                timeout=30,
                check=True,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        return out if out.exists() else None


class PiperTTS:
    """Local TTS via piper. Higher quality than espeak."""

    VOICES_DIR = Path.home() / ".local" / "share" / "piper" / "voices"

    def __init__(self, voice: str = "es_ES-mls_10246-low") -> None:
        self.voice = voice
        self._bin = shutil.which("piper")

    def _resolve_model(self, voice: str) -> str:
        """Resolve voice name to full .onnx path if it exists."""
        model_path = self.VOICES_DIR / f"{voice}.onnx"
        if model_path.exists():
            return str(model_path)
        return voice  # fallback to raw name (piper may auto-download)

    def speak(self, text: str, voice: str | None = None) -> Path | None:
        if not self._bin:
            return None
        voice = voice or self.voice
        model = self._resolve_model(voice)
        out = Path(tempfile.mktemp(suffix=".wav", prefix="nanito_tts_"))
        try:
            subprocess.run(
                [self._bin, "--model", model, "--output_file", str(out)],
                input=text,
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        return out if out.exists() else None


# ---------------------------------------------------------------------------
# STT providers
# ---------------------------------------------------------------------------

@runtime_checkable
class STTProvider(Protocol):
    def transcribe(self, audio_path: Path) -> str | None: ...


class VoskSTT:
    """Lightweight CPU-based STT via vosk.

    Requires ``pip install vosk`` and a model download.
    Returns None if vosk is not installed or model is missing.
    """

    def __init__(self, model_path: str | None = None) -> None:
        self._model_path = model_path
        self._available: bool | None = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import vosk  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False
        return self._available

    def transcribe(self, audio_path: Path) -> str | None:
        if not self._check_available():
            return None
        if not audio_path.exists():
            return None
        try:
            import json as _json
            import wave

            import vosk

            model_path = self._model_path
            if model_path is None:
                model_path = str(Path.home() / ".cache" / "vosk" / "model")
            if not Path(model_path).exists():
                return None

            model = vosk.Model(model_path)
            wf = wave.open(str(audio_path), "rb")
            rec = vosk.KaldiRecognizer(model, wf.getframerate())

            results: list[str] = []
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if rec.AcceptWaveform(data):
                    part = _json.loads(rec.Result())
                    if part.get("text"):
                        results.append(part["text"])

            final = _json.loads(rec.FinalResult())
            if final.get("text"):
                results.append(final["text"])

            wf.close()
            return " ".join(results) if results else None
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Notification channels
# ---------------------------------------------------------------------------

@runtime_checkable
class NotificationChannel(Protocol):
    def notify(self, message: str, audio_path: Path | None = None) -> bool: ...


class TerminalNotifier:
    """Always-available channel: prints to stderr + optionally plays audio."""

    def __init__(self, tts: TTSProvider | None = None) -> None:
        self.tts = tts

    def notify(self, message: str, audio_path: Path | None = None) -> bool:
        import sys
        print(f"[nanito] {message}", file=sys.stderr)
        if audio_path and shutil.which("aplay"):
            try:
                subprocess.run(
                    ["aplay", "-q", str(audio_path)],
                    capture_output=True,
                    timeout=30,
                )
            except (subprocess.SubprocessError, OSError):
                pass
        return True


class WhatsAppNotifier:
    """Sends notifications via WhatsApp MCP (claude CLI subprocess)."""

    def __init__(self, phone: str) -> None:
        self.phone = phone

    def notify(self, message: str, audio_path: Path | None = None) -> bool:
        claude_bin = shutil.which("claude")
        if not claude_bin:
            return False
        try:
            # Send text message via MCP tool call
            cmd = [
                claude_bin, "--print", "--tool-use-only",
                "-p", f'Use mcp__whatsapp__send_message to send "{message}" to {self.phone}',
            ]
            subprocess.run(cmd, capture_output=True, timeout=30)
            # Optionally send audio
            if audio_path and audio_path.exists():
                audio_cmd = [
                    claude_bin, "--print", "--tool-use-only",
                    "-p",
                    f"Use mcp__whatsapp__send_audio_message to send the file "
                    f"{audio_path} to {self.phone}",
                ]
                subprocess.run(audio_cmd, capture_output=True, timeout=30)
            return True
        except (subprocess.SubprocessError, OSError):
            return False


# ---------------------------------------------------------------------------
# Main voice interface
# ---------------------------------------------------------------------------

class NanitoVoice:
    """Unified voice interface. Works even with zero audio tools installed."""

    def __init__(
        self,
        tts: TTSProvider | None = None,
        stt: STTProvider | None = None,
        channels: list[NotificationChannel] | None = None,
    ) -> None:
        self.tts = tts
        self.stt = stt
        self.channels = channels or []

    @classmethod
    def auto_detect(cls) -> NanitoVoice:
        """Detect available TTS/STT providers and notification channels."""
        # TTS: prefer piper > espeak
        tts: TTSProvider | None = None
        if shutil.which("piper"):
            tts = PiperTTS()
        elif shutil.which("espeak"):
            tts = EspeakTTS()

        # STT: vosk (CPU-friendly)
        stt: STTProvider | None = None
        vosk_stt = VoskSTT()
        if vosk_stt._check_available():
            stt = vosk_stt

        # Channels: terminal always, whatsapp if claude CLI exists
        channels: list[NotificationChannel] = [TerminalNotifier(tts=tts)]
        if shutil.which("claude"):
            channels.append(WhatsAppNotifier(phone="default"))

        return cls(tts=tts, stt=stt, channels=channels)

    def announce(self, message: str) -> None:
        """Generate TTS audio and send to all notification channels."""
        audio_path: Path | None = None
        if self.tts:
            audio_path = self.tts.speak(message)
        for channel in self.channels:
            try:
                channel.notify(message, audio_path=audio_path)
            except Exception:
                pass  # Never crash on notification failure

    def listen(self, audio_path: Path) -> str | None:
        """Transcribe audio file via STT."""
        if not self.stt:
            return None
        return self.stt.transcribe(audio_path)

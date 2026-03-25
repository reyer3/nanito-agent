"""Tests for the voice module — TTS, STT, and notification abstractions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nanito_agent.voice import (
    EspeakTTS,
    NanitoVoice,
    PiperTTS,
    TerminalNotifier,
    VoskSTT,
    WhatsAppNotifier,
)


# ---------------------------------------------------------------------------
# TTS tests
# ---------------------------------------------------------------------------


class TestEspeakTTS:
    def test_espeak_available(self, tmp_path):
        """EspeakTTS produces a file when espeak binary exists."""
        wav = tmp_path / "nanito_tts_test.wav"
        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/espeak"),
            patch("nanito_agent.voice.subprocess.run") as mock_run,
            patch("nanito_agent.voice.tempfile.mktemp", return_value=str(wav)),
        ):
            wav.write_bytes(b"RIFF" + b"\x00" * 40)  # fake wav
            tts = EspeakTTS(lang="es")
            result = tts.speak("hola mundo")

        assert result is not None
        assert result.exists()
        mock_run.assert_called_once()

    def test_espeak_not_available(self):
        """EspeakTTS returns None when espeak is not installed."""
        with patch("nanito_agent.voice.shutil.which", return_value=None):
            tts = EspeakTTS()
            result = tts.speak("hello")
        assert result is None

    def test_espeak_subprocess_error(self, tmp_path):
        """EspeakTTS returns None when subprocess fails."""
        import subprocess

        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/espeak"),
            patch(
                "nanito_agent.voice.subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "espeak"),
            ),
        ):
            tts = EspeakTTS()
            result = tts.speak("hello")
        assert result is None


class TestPiperTTS:
    def test_piper_available(self, tmp_path):
        """PiperTTS produces a file when piper binary exists."""
        wav = tmp_path / "nanito_tts_test.wav"
        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/piper"),
            patch("nanito_agent.voice.subprocess.run") as mock_run,
            patch("nanito_agent.voice.tempfile.mktemp", return_value=str(wav)),
        ):
            wav.write_bytes(b"RIFF" + b"\x00" * 40)
            tts = PiperTTS()
            result = tts.speak("hola mundo")

        assert result is not None
        mock_run.assert_called_once()

    def test_piper_not_available(self):
        """PiperTTS returns None when piper is not installed."""
        with patch("nanito_agent.voice.shutil.which", return_value=None):
            tts = PiperTTS()
            result = tts.speak("hello")
        assert result is None

    def test_piper_custom_voice(self, tmp_path):
        """PiperTTS accepts a custom voice parameter."""
        wav = tmp_path / "nanito_tts_test.wav"
        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/piper"),
            patch("nanito_agent.voice.subprocess.run") as mock_run,
            patch("nanito_agent.voice.tempfile.mktemp", return_value=str(wav)),
        ):
            wav.write_bytes(b"RIFF" + b"\x00" * 40)
            tts = PiperTTS(voice="en_US-lessac-medium")
            result = tts.speak("hello world", voice="en_US-lessac-high")

        args = mock_run.call_args[0][0]
        assert "en_US-lessac-high" in args


# ---------------------------------------------------------------------------
# STT tests
# ---------------------------------------------------------------------------


class TestVoskSTT:
    def test_vosk_available(self, tmp_path):
        """VoskSTT returns transcription when vosk is installed and model exists."""
        mock_vosk = MagicMock()
        mock_model = MagicMock()
        mock_vosk.Model.return_value = mock_model
        mock_rec = MagicMock()
        mock_vosk.KaldiRecognizer.return_value = mock_rec
        mock_rec.AcceptWaveform.return_value = False
        mock_rec.FinalResult.return_value = '{"text": "hola mundo"}'

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"RIFF" + b"\x00" * 40)

        import wave
        mock_wf = MagicMock()
        mock_wf.getframerate.return_value = 16000
        mock_wf.readframes.side_effect = [b"\x00" * 8000, b""]

        with (
            patch.dict("sys.modules", {"vosk": mock_vosk}),
            patch("wave.open", return_value=mock_wf),
        ):
            stt = VoskSTT(model_path=str(tmp_path / "model"))
            (tmp_path / "model").mkdir()
            stt._available = None  # reset cache
            result = stt.transcribe(audio_file)

        assert result == "hola mundo"

    def test_vosk_not_available(self):
        """VoskSTT returns None when vosk is not installed."""
        stt = VoskSTT()
        stt._available = False
        result = stt.transcribe(Path("/nonexistent/audio.wav"))
        assert result is None

    def test_vosk_missing_audio_file(self, tmp_path):
        """VoskSTT returns None for nonexistent audio file."""
        stt = VoskSTT()
        stt._available = True
        result = stt.transcribe(tmp_path / "does_not_exist.wav")
        assert result is None


# ---------------------------------------------------------------------------
# Notification channel tests
# ---------------------------------------------------------------------------


class TestTerminalNotifier:
    def test_terminal_notifier_always_works(self, capsys):
        """TerminalNotifier prints to stderr regardless of audio tools."""
        notifier = TerminalNotifier(tts=None)
        result = notifier.notify("Session started")
        assert result is True
        captured = capsys.readouterr()
        assert "[nanito] Session started" in captured.err

    def test_terminal_notifier_with_audio(self, tmp_path):
        """TerminalNotifier attempts playback when aplay exists."""
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"fake")
        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/aplay"),
            patch("nanito_agent.voice.subprocess.run") as mock_run,
        ):
            notifier = TerminalNotifier(tts=None)
            notifier.notify("test", audio_path=audio)
        mock_run.assert_called_once()


class TestWhatsAppNotifier:
    def test_whatsapp_notifier_sends_message(self):
        """WhatsAppNotifier calls claude CLI to send message."""
        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/claude"),
            patch("nanito_agent.voice.subprocess.run") as mock_run,
        ):
            notifier = WhatsAppNotifier(phone="+56912345678")
            result = notifier.notify("Test message")

        assert result is True
        mock_run.assert_called_once()

    def test_whatsapp_notifier_no_claude(self):
        """WhatsAppNotifier returns False when claude CLI is not available."""
        with patch("nanito_agent.voice.shutil.which", return_value=None):
            notifier = WhatsAppNotifier(phone="+56912345678")
            result = notifier.notify("Test message")
        assert result is False

    def test_whatsapp_notifier_with_audio(self, tmp_path):
        """WhatsAppNotifier sends both text and audio when audio path provided."""
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"fake")
        with (
            patch("nanito_agent.voice.shutil.which", return_value="/usr/bin/claude"),
            patch("nanito_agent.voice.subprocess.run") as mock_run,
        ):
            notifier = WhatsAppNotifier(phone="+56912345678")
            notifier.notify("Test", audio_path=audio)

        assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# NanitoVoice integration tests
# ---------------------------------------------------------------------------


class TestNanitoVoice:
    def test_auto_detect_with_nothing_installed(self):
        """auto_detect returns valid NanitoVoice with terminal-only when nothing is installed."""
        with patch("nanito_agent.voice.shutil.which", return_value=None):
            voice = NanitoVoice.auto_detect()

        assert voice.tts is None
        assert voice.stt is None
        assert len(voice.channels) == 1
        assert isinstance(voice.channels[0], TerminalNotifier)

    def test_auto_detect_with_espeak(self):
        """auto_detect picks espeak when only espeak is available."""
        def mock_which(name):
            return "/usr/bin/espeak" if name == "espeak" else None

        with patch("nanito_agent.voice.shutil.which", side_effect=mock_which):
            voice = NanitoVoice.auto_detect()

        assert isinstance(voice.tts, EspeakTTS)
        assert voice.stt is None

    def test_auto_detect_prefers_piper(self):
        """auto_detect prefers piper over espeak when both are available."""
        def mock_which(name):
            if name in ("piper", "espeak"):
                return f"/usr/bin/{name}"
            return None

        with patch("nanito_agent.voice.shutil.which", side_effect=mock_which):
            voice = NanitoVoice.auto_detect()

        assert isinstance(voice.tts, PiperTTS)

    def test_announce_with_no_tts(self, capsys):
        """announce sends text-only notification when no TTS is available."""
        voice = NanitoVoice(tts=None, stt=None, channels=[TerminalNotifier()])
        voice.announce("Test announcement")
        captured = capsys.readouterr()
        assert "[nanito] Test announcement" in captured.err

    def test_announce_with_tts(self, tmp_path):
        """announce generates audio and passes it to channels."""
        wav = tmp_path / "test.wav"
        wav.write_bytes(b"RIFF" + b"\x00" * 40)

        mock_tts = MagicMock()
        mock_tts.speak.return_value = wav
        mock_channel = MagicMock()
        mock_channel.notify.return_value = True

        voice = NanitoVoice(tts=mock_tts, stt=None, channels=[mock_channel])
        voice.announce("hello")

        mock_tts.speak.assert_called_once_with("hello")
        mock_channel.notify.assert_called_once_with("hello", audio_path=wav)

    def test_announce_channel_failure_does_not_crash(self):
        """announce swallows channel exceptions silently."""
        mock_channel = MagicMock()
        mock_channel.notify.side_effect = RuntimeError("boom")

        voice = NanitoVoice(tts=None, stt=None, channels=[mock_channel])
        voice.announce("should not crash")  # no exception raised

    def test_listen_without_stt(self):
        """listen returns None when no STT provider is configured."""
        voice = NanitoVoice(tts=None, stt=None, channels=[])
        result = voice.listen(Path("/fake/audio.wav"))
        assert result is None

    def test_listen_with_stt(self, tmp_path):
        """listen delegates to STT provider."""
        audio = tmp_path / "test.wav"
        audio.write_bytes(b"fake")
        mock_stt = MagicMock()
        mock_stt.transcribe.return_value = "transcribed text"

        voice = NanitoVoice(tts=None, stt=mock_stt, channels=[])
        result = voice.listen(audio)

        assert result == "transcribed text"
        mock_stt.transcribe.assert_called_once_with(audio)

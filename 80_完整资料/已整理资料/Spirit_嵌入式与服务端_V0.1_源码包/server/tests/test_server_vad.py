from __future__ import annotations

from usaki_server.audio.providers import AudioFormat
from usaki_server.audio.vad import VadDecision
from usaki_server.audio.voice_session import UtteranceBuffer
from usaki_server.config import Settings


class FakeVadDetector:
    def __init__(self, decisions: list[VadDecision]) -> None:
        self._decisions = decisions
        self.reset_count = 0

    def accept_pcm(self, pcm_s16le: bytes, *, now_ms: float | None = None) -> VadDecision:
        if self._decisions:
            return self._decisions.pop(0)
        return VadDecision(have_voice=False, should_finalize=False)

    def reset(self) -> None:
        self.reset_count += 1


def test_utterance_buffer_uses_server_vad_endpoint() -> None:
    detector = FakeVadDetector(
        [
            VadDecision(have_voice=False, should_finalize=False, speech_prob=0.1),
            VadDecision(have_voice=True, should_finalize=False, speech_prob=0.8),
            VadDecision(have_voice=False, should_finalize=True, speech_prob=0.1),
        ]
    )
    buffer = UtteranceBuffer(
        Settings(audio_vad_provider="rms"),
        AudioFormat(sample_rate_hz=16000, sample_format="opus"),
        vad_detector=detector,
    )
    pcm = b"\x00\x00" * 960

    assert buffer.append(b"silent", pcm) is False
    assert buffer.append(b"speech", pcm) is False
    assert buffer.append(b"end", pcm) is True

    assert buffer.pop_transport() == [b"silent", b"speech", b"end"]
    assert detector.reset_count == 1


def test_utterance_buffer_keeps_audio_when_external_vad_already_started() -> None:
    detector = FakeVadDetector(
        [VadDecision(have_voice=False, should_finalize=False, speech_prob=0.1)] * 15
    )
    buffer = UtteranceBuffer(
        Settings(audio_vad_provider="rms"),
        AudioFormat(sample_rate_hz=16000, sample_format="opus"),
        vad_detector=detector,
    )
    buffer.begin_utterance(trust_external_vad=True)
    pcm = b"\x00\x00" * 960

    for index in range(15):
        assert buffer.append(f"packet-{index}".encode("ascii"), pcm) is False

    assert buffer.has_voice() is False
    assert len(buffer.pop_pcm()) == 15
    assert detector.reset_count == 2

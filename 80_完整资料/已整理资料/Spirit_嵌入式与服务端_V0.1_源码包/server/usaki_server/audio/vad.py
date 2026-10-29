from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import logging
from pathlib import Path
import time
from typing import Protocol

from usaki_server.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VadDecision:
    have_voice: bool
    should_finalize: bool
    speech_prob: float | None = None


class ServerVadDetector(Protocol):
    def accept_pcm(self, pcm_s16le: bytes, *, now_ms: float | None = None) -> VadDecision:
        ...

    def reset(self) -> None:
        ...


class SileroVadDetector:
    """Streaming Silero VAD endpoint detector, adapted from xiaozhi-server.

    The detector consumes 16 kHz mono pcm_s16le chunks. It keeps per-session ONNX
    recurrent state and reports an utterance end after speech has been followed by
    enough silence.
    """

    _WINDOW_SAMPLES = 512
    _CONTEXT_SAMPLES = 64

    def __init__(
        self,
        *,
        model_path: Path,
        threshold: float = 0.5,
        threshold_low: float = 0.3,
        min_silence_duration_ms: int = 200,
        frame_window_threshold: int = 3,
    ) -> None:
        import numpy as np  # type: ignore
        import onnxruntime  # type: ignore

        if not model_path.exists():
            raise FileNotFoundError(f"Silero VAD model not found: {model_path}")

        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self._session = onnxruntime.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
            sess_options=opts,
        )
        self._np = np
        self._threshold = threshold
        self._threshold_low = threshold_low
        self._min_silence_duration_ms = min_silence_duration_ms
        self._frame_window_threshold = frame_window_threshold
        self._pcm_buffer = bytearray()
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, self._CONTEXT_SAMPLES), dtype=np.float32)
        self._voice_window: deque[bool] = deque(maxlen=5)
        self._last_is_voice = False
        self._has_voice = False
        self._last_voice_time_ms = 0.0

    def accept_pcm(self, pcm_s16le: bytes, *, now_ms: float | None = None) -> VadDecision:
        if not pcm_s16le:
            return VadDecision(have_voice=False, should_finalize=False)

        now_ms = now_ms if now_ms is not None else time.time() * 1000
        self._pcm_buffer.extend(pcm_s16le)
        client_have_voice = False
        should_finalize = False
        last_prob: float | None = None
        window_bytes = self._WINDOW_SAMPLES * 2

        while len(self._pcm_buffer) >= window_bytes:
            chunk = self._pcm_buffer[:window_bytes]
            del self._pcm_buffer[:window_bytes]

            audio_int16 = self._np.frombuffer(chunk, dtype=self._np.int16)
            audio_float32 = audio_int16.astype(self._np.float32) / 32768.0
            audio_input = self._np.concatenate(
                [self._context, audio_float32.reshape(1, -1)],
                axis=1,
            ).astype(self._np.float32)

            out, state = self._session.run(
                None,
                {
                    "input": audio_input,
                    "state": self._state,
                    "sr": self._np.array(16000, dtype=self._np.int64),
                },
            )
            self._state = state
            self._context = audio_input[:, -self._CONTEXT_SAMPLES :]
            speech_prob = float(out.item())
            last_prob = speech_prob

            if speech_prob >= self._threshold:
                is_voice = True
            elif speech_prob <= self._threshold_low:
                is_voice = False
            else:
                is_voice = self._last_is_voice

            self._last_is_voice = is_voice
            self._voice_window.append(is_voice)
            client_have_voice = (
                self._voice_window.count(True) >= self._frame_window_threshold
            )

            if self._has_voice and not client_have_voice:
                stop_duration = now_ms - self._last_voice_time_ms
                if stop_duration >= self._min_silence_duration_ms:
                    should_finalize = True

            if client_have_voice:
                self._has_voice = True
                self._last_voice_time_ms = now_ms

        return VadDecision(
            have_voice=client_have_voice,
            should_finalize=should_finalize,
            speech_prob=last_prob,
        )

    def reset(self) -> None:
        self._pcm_buffer.clear()
        self._state = self._np.zeros((2, 1, 128), dtype=self._np.float32)
        self._context = self._np.zeros((1, self._CONTEXT_SAMPLES), dtype=self._np.float32)
        self._voice_window.clear()
        self._last_is_voice = False
        self._has_voice = False
        self._last_voice_time_ms = 0.0


def create_server_vad_detector(settings: Settings) -> ServerVadDetector | None:
    provider = settings.audio_vad_provider.strip().lower()
    if provider in {"", "none", "off", "disabled", "rms"}:
        return None
    if provider != "silero":
        raise ValueError(f"unsupported audio_vad_provider: {settings.audio_vad_provider}")

    model_path = Path(settings.audio_vad_model_path) if settings.audio_vad_model_path else None
    if model_path is None:
        model_path = default_silero_model_path()

    try:
        detector = SileroVadDetector(
            model_path=model_path,
            threshold=settings.audio_vad_threshold,
            threshold_low=settings.audio_vad_threshold_low,
            min_silence_duration_ms=settings.audio_vad_min_silence_duration_ms,
            frame_window_threshold=settings.audio_vad_frame_window_threshold,
        )
        logger.warning("[USAKI DIAG] using Silero server VAD model=%s", model_path)
        return detector
    except Exception as exc:
        logger.warning("[USAKI DIAG] Silero server VAD unavailable, using RMS fallback: %s", exc)
        return None


def default_silero_model_path() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    return (
        repo_root
        / "xiaozhi"
        / "xiaozhi-esp32-server"
        / "main"
        / "xiaozhi-server"
        / "models"
        / "snakers4_silero-vad"
        / "src"
        / "silero_vad"
        / "data"
        / "silero_vad.onnx"
    )

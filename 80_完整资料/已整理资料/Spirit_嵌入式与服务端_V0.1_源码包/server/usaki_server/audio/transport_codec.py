from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import sys

logger = logging.getLogger(__name__)

DEFAULT_OPUS_FRAME_DURATION_MS = 60
PCM_SAMPLE_BITS = 16


@dataclass(frozen=True)
class TransportAudioFormat:
    codec: str = "opus"
    sample_rate_hz: int = 16000
    channels: int = 1
    sample_bits: int = PCM_SAMPLE_BITS
    frame_duration_ms: int = DEFAULT_OPUS_FRAME_DURATION_MS

    @property
    def pcm_frame_bytes(self) -> int:
        return (
            self.sample_rate_hz
            * self.channels
            * (self.sample_bits // 8)
            * self.frame_duration_ms
            // 1000
        )


class TransportAudioCodec:
    def __init__(self, audio_format: TransportAudioFormat) -> None:
        self.format = audio_format

    def decode(self, packet: bytes) -> bytes:
        raise NotImplementedError

    def encode_pcm_stream(self, pcm: bytes) -> list[bytes]:
        raise NotImplementedError

    def flush(self) -> list[bytes]:
        return []


class OpusTransportCodec(TransportAudioCodec):
    def __init__(self, audio_format: TransportAudioFormat) -> None:
        super().__init__(audio_format)
        self._pcm_tail = b""
        self._encoder = None
        self._decoder = None
        try:
            _prepare_opus_dll_search_path()
            import opuslib_next  # type: ignore

            self._opuslib = opuslib_next
            self._encoder = opuslib_next.Encoder(
                audio_format.sample_rate_hz,
                audio_format.channels,
                "audio",
            )
            self._decoder = opuslib_next.Decoder(
                audio_format.sample_rate_hz,
                audio_format.channels,
            )
        except Exception as exc:
            self._opuslib = None
            logger.warning("opuslib-next is unavailable, Opus transport disabled: %s", exc)

    def decode(self, packet: bytes) -> bytes:
        if not packet:
            return b""
        if self._decoder is None:
            raise RuntimeError("Opus transport requires opuslib-next to decode audio")
        frame_size = self.format.sample_rate_hz * self.format.frame_duration_ms // 1000
        return self._decoder.decode(packet, frame_size)

    def encode_pcm_stream(self, pcm: bytes) -> list[bytes]:
        if not pcm:
            return []
        if self._encoder is None:
            raise RuntimeError("Opus transport requires opuslib-next to encode audio")

        data = self._pcm_tail + pcm
        frame_bytes = self.format.pcm_frame_bytes
        packets: list[bytes] = []
        offset = 0
        while offset + frame_bytes <= len(data):
            frame = data[offset : offset + frame_bytes]
            packets.append(self._encoder.encode(frame, frame_bytes // 2))
            offset += frame_bytes
        self._pcm_tail = data[offset:]
        return packets

    def flush(self) -> list[bytes]:
        if not self._pcm_tail:
            return []
        if self._encoder is None:
            raise RuntimeError("Opus transport requires opuslib-next to encode audio")
        frame_bytes = self.format.pcm_frame_bytes
        padded = self._pcm_tail + b"\x00" * (frame_bytes - len(self._pcm_tail))
        self._pcm_tail = b""
        return [self._encoder.encode(padded, frame_bytes // 2)]


def create_transport_codec(audio_format: TransportAudioFormat) -> TransportAudioCodec:
    codec = audio_format.codec.lower()
    if codec == "opus":
        return OpusTransportCodec(audio_format)
    raise ValueError(f"unsupported transport codec: {audio_format.codec}; only opus is supported")


def _prepare_opus_dll_search_path() -> None:
    if os.name != "nt":
        return

    candidates = [
        os.path.join(sys.prefix, "Library", "bin"),
        os.path.join(sys.prefix, "bin"),
    ]
    for path in candidates:
        if not os.path.isdir(path):
            continue
        if path not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = path + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(path)

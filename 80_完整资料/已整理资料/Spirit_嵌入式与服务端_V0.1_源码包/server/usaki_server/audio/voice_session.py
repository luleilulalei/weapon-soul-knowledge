from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
import math
import struct
import time

from usaki_server.audio.providers import AudioFormat, VoiceProviders
from usaki_server.audio.transport_codec import (
    DEFAULT_OPUS_FRAME_DURATION_MS,
    TransportAudioCodec,
    TransportAudioFormat,
    create_transport_codec,
)
from usaki_server.audio.vad import ServerVadDetector, create_server_vad_detector
from usaki_server.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssistantAudioChunk:
    text: str
    audio: bytes


class UtteranceBuffer:
    # Keep up to 600 ms of pre-speech audio, matching xiaozhi's 10-frame strategy.
    _MAX_SILENT_PREAMBLE_FRAMES = 10

    def __init__(
        self,
        settings: Settings,
        audio_format: AudioFormat,
        vad_detector: ServerVadDetector | None = None,
    ) -> None:
        self._settings = settings
        self._audio_format = audio_format
        self._vad_detector = vad_detector
        self._transport_chunks: list[bytes] = []
        self._pcm_chunks: list[bytes] = []
        self._started_at = time.monotonic()
        self._last_voice_at: float | None = None
        self._has_voice = False
        self._keep_audio_from_start = False

    def begin_utterance(self, *, trust_external_vad: bool = False) -> None:
        self._reset()
        self._keep_audio_from_start = trust_external_vad

    def append(self, transport_chunk: bytes, pcm_chunk: bytes) -> bool:
        if not transport_chunk:
            return False

        now = time.monotonic()
        rms = _pcm_s16le_rms(pcm_chunk)
        vad_decision = (
            self._vad_detector.accept_pcm(pcm_chunk, now_ms=now * 1000)
            if self._vad_detector is not None
            else None
        )
        has_voice = (
            vad_decision.have_voice
            if vad_decision is not None
            else rms >= self._settings.audio_silence_rms_threshold
        )

        if not self._has_voice:
            self._append_chunk(transport_chunk, pcm_chunk)
            if has_voice:
                self._last_voice_at = now
                self._has_voice = True
            else:
                if not self._keep_audio_from_start:
                    self._trim_silent_preamble()
                return False
        else:
            self._append_chunk(transport_chunk, pcm_chunk)

        if has_voice:
            self._last_voice_at = now

        silence_ms = (now - self._last_voice_at) * 1000 if self._last_voice_at is not None else 0
        utterance_ms = (now - self._started_at) * 1000
        endpoint_detected = (
            vad_decision.should_finalize
            if vad_decision is not None
            else silence_ms >= self._settings.audio_silence_timeout_ms
        )
        should_finalize = endpoint_detected or utterance_ms >= self._settings.audio_max_utterance_ms
        if should_finalize:
            logger.warning(
                "[USAKI DIAG] UtteranceBuffer finalize: silence_ms=%.0f utterance_ms=%.0f "
                "thresholds(silence=%.0f, max_utterance=%.0f) rms=%d vad_prob=%s chunks=%d",
                silence_ms,
                utterance_ms,
                self._settings.audio_silence_timeout_ms,
                self._settings.audio_max_utterance_ms,
                rms,
                (
                    f"{vad_decision.speech_prob:.3f}"
                    if vad_decision and vad_decision.speech_prob is not None
                    else "n/a"
                ),
                len(self._transport_chunks),
            )
        return should_finalize

    def has_voice(self) -> bool:
        return self._has_voice

    def has_audio(self) -> bool:
        return bool(self._transport_chunks)

    def pop_pcm(self) -> list[bytes]:
        chunks = list(self._pcm_chunks)
        self._reset()
        return chunks

    def pop_transport(self) -> list[bytes]:
        chunks = list(self._transport_chunks)
        logger.warning(
            "[USAKI DIAG] UtteranceBuffer pop_transport: returning %d chunks (%.1f seconds of audio)",
            len(chunks),
            len(chunks) * self._audio_format.sample_rate_hz * 0.02 / self._audio_format.sample_rate_hz
            if self._audio_format.sample_rate_hz
            else 0,
        )
        self._reset()
        return chunks

    def _append_chunk(self, transport_chunk: bytes, pcm_chunk: bytes) -> None:
        self._transport_chunks.append(transport_chunk)
        if pcm_chunk:
            self._pcm_chunks.append(pcm_chunk)

    def _trim_silent_preamble(self) -> None:
        if len(self._transport_chunks) <= self._MAX_SILENT_PREAMBLE_FRAMES:
            return
        self._transport_chunks = self._transport_chunks[-self._MAX_SILENT_PREAMBLE_FRAMES :]
        if self._pcm_chunks:
            self._pcm_chunks = self._pcm_chunks[-self._MAX_SILENT_PREAMBLE_FRAMES :]

    def _reset(self) -> None:
        self._transport_chunks.clear()
        self._pcm_chunks.clear()
        self._started_at = time.monotonic()
        self._last_voice_at = None
        self._has_voice = False
        self._keep_audio_from_start = False
        if self._vad_detector is not None:
            self._vad_detector.reset()


class VoiceSession:
    def __init__(self, settings: Settings, providers: VoiceProviders) -> None:
        self.audio_format = AudioFormat(
            sample_rate_hz=settings.audio_sample_rate_hz,
            sample_format="opus",
        )
        self.pcm_audio_format = AudioFormat(
            sample_rate_hz=settings.audio_sample_rate_hz,
            sample_format="pcm_s16le",
        )
        self.tts_audio_format = AudioFormat(sample_rate_hz=settings.audio_sample_rate_hz)
        self._buffer = UtteranceBuffer(
            settings,
            self.audio_format,
            vad_detector=create_server_vad_detector(settings),
        )
        self._providers = providers
        self._input_format = TransportAudioFormat(
            codec="opus",
            sample_rate_hz=settings.audio_sample_rate_hz,
            frame_duration_ms=DEFAULT_OPUS_FRAME_DURATION_MS,
        )
        self._input_codec: TransportAudioCodec = create_transport_codec(self._input_format)
        self._input_voice_logged = False

    def configure_input(self, audio_format: TransportAudioFormat) -> None:
        self._input_format = audio_format
        self._input_codec = create_transport_codec(audio_format)

    def begin_input(self, *, trust_external_vad: bool = False) -> None:
        self._buffer.begin_utterance(trust_external_vad=trust_external_vad)
        self._input_voice_logged = False

    def append_audio(self, chunk: bytes) -> bool:
        pcm = self._input_codec.decode(chunk)
        result = self._buffer.append(chunk, pcm)
        has_voice = self._buffer.has_voice()
        if result or (has_voice and not self._input_voice_logged):
            logger.warning(
                "[USAKI DIAG] VoiceSession append_audio: opus_chunk=%dB pcm_chunk=%dB "
                "vad_finalized=%s",
                len(chunk),
                len(pcm),
                result,
            )
        if has_voice:
            self._input_voice_logged = True
        return result

    def has_audio(self) -> bool:
        return self._buffer.has_audio()

    def pop_audio(self) -> list[bytes]:
        return self._buffer.pop_transport()

    def pop_pcm(self) -> list[bytes]:
        return self._buffer.pop_pcm()

    async def transcribe_buffered_audio(self) -> str:
        pcm_frames = self.pop_pcm()
        combined_pcm = b"".join(pcm_frames)
        pcm_ms = (
            len(combined_pcm)
            * 1000
            // (
                self.pcm_audio_format.sample_rate_hz
                * self.pcm_audio_format.channels
                * 2
            )
            if self.pcm_audio_format.sample_rate_hz and self.pcm_audio_format.channels
            else 0
        )
        frame_rms = [_pcm_s16le_rms(frame) for frame in pcm_frames if frame]
        avg_rms = int(sum(frame_rms) / len(frame_rms)) if frame_rms else 0
        max_rms = max(frame_rms) if frame_rms else 0
        logger.warning(
            "[USAKI DIAG] transcribe_buffered_audio: pcm_frames=%d total_bytes=%d "
            "pcm_ms=%d rms_avg=%d rms_max=%d stt_provider=%s",
            len(pcm_frames),
            len(combined_pcm),
            pcm_ms,
            avg_rms,
            max_rms,
            type(self._providers.stt).__name__,
        )
        result = (await self._providers.stt.transcribe(combined_pcm, self.pcm_audio_format)).strip()
        logger.warning(
            "[USAKI DIAG] transcribe_buffered_audio result: text=[%s] len=%d",
            result,
            len(result),
        )
        return result

    async def respond(self, device_id: str) -> tuple[str, str, bytes]:
        user_text = await self.transcribe_buffered_audio()
        logger.warning("[USAKI DIAG] respond user_text=[%s]", user_text)
        return await self.respond_from_text(user_text, device_id)

    async def respond_from_text(self, user_text: str, device_id: str) -> tuple[str, str, bytes]:
        user_text = user_text.strip()
        if not user_text:
            logger.warning("[USAKI DIAG] respond_from_text: empty user_text, returning early")
            return "", "", b""
        assistant_text_parts: list[str] = []
        audio_parts: list[bytes] = []
        async for chunk in self.stream_response_from_text(user_text, device_id):
            assistant_text_parts.append(chunk.text)
            if chunk.audio:
                audio_parts.append(chunk.audio)
        assistant_text = "".join(assistant_text_parts).strip()
        logger.warning(
            "[USAKI DIAG] respond_from_text done user=[%s] assistant=[%s]",
            user_text,
            assistant_text,
        )
        return user_text, assistant_text, b"".join(audio_parts)

    async def stream_response_from_text(
        self, user_text: str, device_id: str
    ) -> AsyncIterator[AssistantAudioChunk]:
        """Stream LLM deltas, cut them into speakable sentences, and synthesize early."""
        user_text = user_text.strip()
        if not user_text:
            logger.warning("[USAKI DIAG] stream_response_from_text: empty text, returning")
            return

        pending = ""
        full_parts: list[str] = []
        llm_delta_count = 0
        llm_started_at = time.perf_counter()
        first_delta_logged = False
        first_sentence_logged = False
        first_tts_audio_logged = False
        logger.warning(
            "[USAKI DIAG] stream_response_from_text: calling LLM user_text=[%s] device_id=%s "
            "llm_provider=%s",
            user_text,
            device_id,
            type(self._providers.llm).__name__,
        )
        async for delta in self._providers.llm.stream_complete(user_text, device_id):
            llm_delta_count += 1
            if not delta:
                continue
            if not first_delta_logged:
                first_delta_logged = True
                logger.warning(
                    "[USAKI PERF] llm_first_delta device_id=%s ms=%.0f",
                    device_id,
                    (time.perf_counter() - llm_started_at) * 1000,
                )
            full_parts.append(delta)
            pending += delta
            while True:
                sentence, pending = _pop_speakable_sentence(pending)
                if not sentence:
                    break
                sentence_started_at = time.perf_counter()
                if not first_sentence_logged:
                    first_sentence_logged = True
                    logger.warning(
                        "[USAKI PERF] first_speakable_sentence device_id=%s ms=%.0f chars=%d",
                        device_id,
                        (sentence_started_at - llm_started_at) * 1000,
                        len(sentence),
                    )
                logger.warning(
                    "[USAKI DIAG] LLM delta[%d] sentence=[%s] (pending_len=%d)",
                    llm_delta_count,
                    sentence,
                    len(pending),
                )
                text_sent = False
                async for audio in self._providers.tts.stream_synthesize(
                    sentence, self.tts_audio_format
                ):
                    if audio and not first_tts_audio_logged:
                        first_tts_audio_logged = True
                        logger.warning(
                            "[USAKI PERF] tts_first_audio device_id=%s since_sentence_ms=%.0f "
                            "since_llm_ms=%.0f bytes=%d",
                            device_id,
                            (time.perf_counter() - sentence_started_at) * 1000,
                            (time.perf_counter() - llm_started_at) * 1000,
                            len(audio),
                        )
                    yield AssistantAudioChunk(
                        text=sentence if not text_sent else "",
                        audio=audio,
                    )
                    text_sent = True
                if not text_sent:
                    logger.warning(
                        "[USAKI DIAG] TTS returned no audio for sentence=[%s]",
                        sentence,
                    )
                    yield AssistantAudioChunk(text=sentence, audio=b"")

        tail = pending.strip()
        if tail:
            logger.warning(
                "[USAKI DIAG] LLM final tail=[%s] (after %d deltas)",
                tail,
                llm_delta_count,
            )
            text_sent = False
            sentence_started_at = time.perf_counter()
            if not first_sentence_logged:
                first_sentence_logged = True
                logger.warning(
                    "[USAKI PERF] first_speakable_sentence device_id=%s ms=%.0f chars=%d",
                    device_id,
                    (sentence_started_at - llm_started_at) * 1000,
                    len(tail),
                )
            async for audio in self._providers.tts.stream_synthesize(tail, self.tts_audio_format):
                if audio and not first_tts_audio_logged:
                    first_tts_audio_logged = True
                    logger.warning(
                        "[USAKI PERF] tts_first_audio device_id=%s since_sentence_ms=%.0f "
                        "since_llm_ms=%.0f bytes=%d",
                        device_id,
                        (time.perf_counter() - sentence_started_at) * 1000,
                        (time.perf_counter() - llm_started_at) * 1000,
                        len(audio),
                    )
                yield AssistantAudioChunk(text=tail if not text_sent else "", audio=audio)
                text_sent = True
            if not text_sent:
                logger.warning(
                    "[USAKI DIAG] TTS returned no audio for final tail=[%s]",
                    tail,
                )
                yield AssistantAudioChunk(text=tail, audio=b"")

        full_text = "".join(full_parts).strip()
        logger.warning(
            "[USAKI DIAG] LLM complete: deltas=%d full_text=[%s]",
            llm_delta_count,
            full_text,
        )

    async def stream_transport_response_from_text(
        self,
        user_text: str,
        device_id: str,
        transport_format: TransportAudioFormat,
    ) -> AsyncIterator[AssistantAudioChunk]:
        encoder = create_transport_codec(transport_format)
        chunk_count = 0
        async for chunk in self.stream_response_from_text(user_text, device_id):
            chunk_count += 1
            if chunk.text:
                logger.warning(
                    "[USAKI DIAG] stream_transport text_chunk[%d]: [%s]",
                    chunk_count,
                    chunk.text,
                )
                yield AssistantAudioChunk(text=chunk.text, audio=b"")
            if not chunk.audio:
                continue
            for packet in encoder.encode_pcm_stream(chunk.audio):
                yield AssistantAudioChunk(text="", audio=packet)
        for packet in encoder.flush():
            yield AssistantAudioChunk(text="", audio=packet)
        logger.warning(
            "[USAKI DIAG] stream_transport complete: total_chunks=%d",
            chunk_count,
        )

    async def stream_transport_fixed_text(
        self,
        text: str,
        transport_format: TransportAudioFormat,
    ) -> AsyncIterator[AssistantAudioChunk]:
        text = text.strip()
        if not text:
            return

        encoder = create_transport_codec(transport_format)
        text_sent = False
        async for audio in self._providers.tts.stream_synthesize(text, self.tts_audio_format):
            if not text_sent:
                yield AssistantAudioChunk(text=text, audio=b"")
                text_sent = True
            if not audio:
                continue
            for packet in encoder.encode_pcm_stream(audio):
                yield AssistantAudioChunk(text="", audio=packet)
        if not text_sent:
            yield AssistantAudioChunk(text=text, audio=b"")
        for packet in encoder.flush():
            yield AssistantAudioChunk(text="", audio=packet)


def _pcm_s16le_rms(chunk: bytes) -> int:
    sample_count = len(chunk) // 2
    if sample_count == 0:
        return 0

    samples = struct.unpack(f"<{sample_count}h", chunk[: sample_count * 2])
    square_sum = sum(sample * sample for sample in samples)
    return int(math.sqrt(square_sum / sample_count))


def _pop_speakable_sentence(text: str) -> tuple[str, str]:
    """Return one sentence-like prefix and the remaining text."""
    stripped = text.lstrip()
    leading_len = len(text) - len(stripped)
    if not stripped:
        return "", ""

    terminators = "。！？!?\n"
    soft_breaks = "，、：:"
    min_soft_len = 12
    max_len = 36

    for index, char in enumerate(stripped):
        if char in terminators:
            end = leading_len + index + 1
            return text[:end].strip(), text[end:]
        if char in soft_breaks and index + 1 >= min_soft_len:
            end = leading_len + index + 1
            return text[:end].strip(), text[end:]

    if len(stripped) >= max_len:
        end = leading_len + max_len
        return text[:end].strip(), text[end:]

    return "", text

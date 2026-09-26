"""Fake providers: no network, no credentials, fixed behaviour.

They serve the tests and a first run in the browser before a real provider
is chosen (#18). The STT "hears" a fixed sentence whenever someone stops
talking, the LLM always gives the same answer, the TTS beeps for as long as
the text would take to say. That is enough to exercise the whole path from
microphone to loudspeaker, including turn detection and latency figures.
"""

from __future__ import annotations

import math
import struct
import uuid

from livekit import rtc
from livekit.agents import llm, stt, tts, utils
from livekit.agents.types import (
    DEFAULT_API_CONNECT_OPTIONS,
    NOT_GIVEN,
    APIConnectOptions,
    NotGivenOr,
)

FAKE_TRANSCRIPT = "Wann haben Sie geöffnet?"
FAKE_REPLY = "Das ist eine Testantwort. Echte Antworten kommen erst mit einem echten Sprachmodell."


def _rms(frame: rtc.AudioFrame) -> float:
    samples = memoryview(frame.data).cast("B").cast("h")
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


class FakeSTT(stt.STT):
    """Streaming STT that reports `transcript` after each stretch of speech.

    Speech is anything louder than `threshold` (RMS of 16-bit samples); it
    ends after `silence` seconds below that.
    """

    def __init__(
        self,
        *,
        transcript: str = FAKE_TRANSCRIPT,
        language: str = "de-DE",
        threshold: float = 500.0,
        silence: float = 0.6,
    ) -> None:
        super().__init__(capabilities=stt.STTCapabilities(streaming=True, interim_results=False))
        self.transcript = transcript
        self.language = language
        self.threshold = threshold
        self.silence = silence

    @property
    def provider(self) -> str:
        return "fake"

    def final_event(self) -> stt.SpeechEvent:
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(language=self.language, text=self.transcript)],
        )

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> stt.SpeechEvent:
        return self.final_event()

    def stream(
        self,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
    ) -> stt.RecognizeStream:
        return _FakeRecognizeStream(stt=self, conn_options=conn_options)


class _FakeRecognizeStream(stt.RecognizeStream):
    _stt: FakeSTT

    async def _run(self) -> None:
        speaking = False
        silent_for = 0.0
        emit = self._event_ch.send_nowait
        async for item in self._input_ch:
            if isinstance(item, self._FlushSentinel):
                loud, duration = False, math.inf
            else:
                loud = _rms(item) >= self._stt.threshold
                duration = item.samples_per_channel / item.sample_rate
            if loud:
                if not speaking:
                    emit(stt.SpeechEvent(type=stt.SpeechEventType.START_OF_SPEECH))
                speaking, silent_for = True, 0.0
            elif speaking:
                silent_for += duration
                if silent_for >= self._stt.silence:
                    emit(self._stt.final_event())
                    emit(stt.SpeechEvent(type=stt.SpeechEventType.END_OF_SPEECH))
                    speaking = False


class FakeLLM(llm.LLM):
    """Answers every turn with `reply`; counts how often it was asked."""

    def __init__(self, *, reply: str = FAKE_REPLY) -> None:
        super().__init__()
        self.reply = reply
        self.calls = 0

    @property
    def provider(self) -> str:
        return "fake"

    def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        tools: list[llm.Tool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        **kwargs: object,
    ) -> llm.LLMStream:
        self.calls += 1
        return _FakeLLMStream(self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options)


class _FakeLLMStream(llm.LLMStream):
    _llm: FakeLLM

    async def _run(self) -> None:
        request_id = str(uuid.uuid4())
        for word in self._llm.reply.split(" "):
            delta = llm.ChoiceDelta(role="assistant", content=word + " ")
            self._event_ch.send_nowait(llm.ChatChunk(id=request_id, delta=delta))


class FakeTTS(tts.TTS):
    """A quiet beep, `seconds_per_char` long per character of text."""

    SAMPLE_RATE = 24000

    def __init__(self, *, seconds_per_char: float = 0.02, max_seconds: float = 10.0) -> None:
        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=False),
            sample_rate=self.SAMPLE_RATE,
            num_channels=1,
        )
        self.seconds_per_char = seconds_per_char
        self.max_seconds = max_seconds

    @property
    def provider(self) -> str:
        return "fake"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts.ChunkedStream:
        return _FakeChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _FakeChunkedStream(tts.ChunkedStream):
    _tts: FakeTTS

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        rate = FakeTTS.SAMPLE_RATE
        seconds = min(len(self._input_text) * self._tts.seconds_per_char, self._tts.max_seconds)
        count = int(seconds * rate)
        tone = (int(2000 * math.sin(2 * math.pi * 440 * i / rate)) for i in range(count))
        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        output_emitter.push(struct.pack(f"<{count}h", *tone))
        output_emitter.flush()

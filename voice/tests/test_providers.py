"""Provider choice by configuration and the fake providers."""

import struct

import pytest
from livekit import rtc
from livekit.agents import llm, stt, tts

from mymvz_voice import providers
from mymvz_voice.config import ConfigError, Settings, load_settings
from mymvz_voice.providers.fake import FAKE_TRANSCRIPT, FakeSTT, FakeTTS


def test_without_variables_all_providers_are_fake():
    assert load_settings({}) == Settings("fake", "fake", "fake", "de-DE")


def test_empty_values_count_as_missing():
    """`VOICE_LLM_PROVIDER=` in .env must not become the provider named ''."""
    settings = load_settings({"VOICE_LLM_PROVIDER": "", "VOICE_LANGUAGE": " "})
    assert settings.llm_provider == "fake"
    assert settings.language == "de-DE"


def test_provider_names_ignore_case_and_blanks():
    assert load_settings({"VOICE_TTS_PROVIDER": " Fake "}).tts_provider == "fake"


def test_builds_the_configured_providers():
    settings = load_settings({})
    assert isinstance(providers.build_stt(settings), stt.STT)
    assert isinstance(providers.build_llm(settings), llm.LLM)
    assert isinstance(providers.build_tts(settings), tts.TTS)


@pytest.mark.parametrize(
    ("variable", "kind"),
    [
        ("VOICE_STT_PROVIDER", "Spracherkennung"),
        ("VOICE_LLM_PROVIDER", "LLM"),
        ("VOICE_TTS_PROVIDER", "Sprachausgabe"),
    ],
)
def test_unknown_provider_is_refused_with_the_known_ones(variable, kind):
    settings = load_settings({variable: "vertex"})
    with pytest.raises(ConfigError, match=rf"{kind}: 'vertex' \(bekannt: fake\)"):
        providers.validate(settings)


def test_unknown_provider_is_refused_when_building():
    with pytest.raises(ConfigError):
        providers.build_llm(load_settings({"VOICE_LLM_PROVIDER": "vertex"}))


def _frame(amplitude: int, seconds: float = 0.1, rate: int = 16000) -> rtc.AudioFrame:
    count = int(seconds * rate)
    data = struct.pack(f"<{count}h", *([amplitude] * count))
    return rtc.AudioFrame(data, rate, 1, count)


async def _events(stream: stt.RecognizeStream, frames, flush: bool = False):
    for frame in frames:
        stream.push_frame(frame)
    if flush:
        stream.flush()
    stream.end_input()
    return [event async for event in stream]


async def test_fake_stt_hears_its_sentence_after_speech_and_silence():
    fake = FakeSTT(silence=0.3)
    events = await _events(fake.stream(), [_frame(3000)] * 5 + [_frame(0)] * 3)
    types = [event.type for event in events]
    assert types == [
        stt.SpeechEventType.START_OF_SPEECH,
        stt.SpeechEventType.FINAL_TRANSCRIPT,
        stt.SpeechEventType.END_OF_SPEECH,
    ]
    assert events[1].alternatives[0].text == FAKE_TRANSCRIPT


async def test_fake_stt_short_pause_does_not_end_the_utterance():
    fake = FakeSTT(silence=0.3)
    frames = [_frame(3000), _frame(0), _frame(0), _frame(3000)] + [_frame(0)] * 3
    events = await _events(fake.stream(), frames)
    assert [event.type for event in events] == [
        stt.SpeechEventType.START_OF_SPEECH,
        stt.SpeechEventType.FINAL_TRANSCRIPT,
        stt.SpeechEventType.END_OF_SPEECH,
    ]


async def test_fake_stt_ignores_quiet_audio():
    fake = FakeSTT()
    assert await _events(fake.stream(), [_frame(100)] * 20) == []


async def test_fake_stt_flush_ends_an_utterance():
    fake = FakeSTT(silence=5.0)
    events = await _events(fake.stream(), [_frame(3000)], flush=True)
    assert events[-1].type == stt.SpeechEventType.END_OF_SPEECH


async def _seconds_of_audio(fake: FakeTTS, text: str) -> float:
    frames = [event.frame async for event in fake.synthesize(text)]
    return sum(f.samples_per_channel for f in frames) / FakeTTS.SAMPLE_RATE


async def test_fake_tts_audio_length_follows_the_text():
    fake = FakeTTS(seconds_per_char=0.01, max_seconds=1.5)
    assert await _seconds_of_audio(fake, "x" * 50) == pytest.approx(0.5, abs=0.05)
    assert await _seconds_of_audio(fake, "x" * 100) == pytest.approx(1.0, abs=0.05)
    assert await _seconds_of_audio(fake, "x" * 500) == pytest.approx(1.5, abs=0.05)

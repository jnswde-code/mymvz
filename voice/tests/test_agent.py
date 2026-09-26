"""The agent end to end, in text mode with the fake LLM.

Text mode skips STT and TTS; what matters here is which turns reach the LLM
and what the caller hears instead when the safety switch fires.
"""

import json

import pytest
from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, AgentSession, llm

from mymvz_voice import texts
from mymvz_voice.agent import ReceptionAgent, build_session
from mymvz_voice.config import load_settings
from mymvz_voice.providers.fake import FAKE_REPLY, FakeLLM, _FakeLLMStream


class ToolCallingLLM(FakeLLM):
    """Answers the first turn with a call of `hand_off(reason)`."""

    def __init__(self, reason: str) -> None:
        super().__init__()
        self.reason = reason

    def chat(self, *, chat_ctx, tools=None, conn_options=DEFAULT_API_CONNECT_OPTIONS, **kwargs):
        self.calls += 1
        return _ToolCallStream(
            self, chat_ctx=chat_ctx, tools=tools or [], conn_options=conn_options
        )


class _ToolCallStream(_FakeLLMStream):
    async def _run(self) -> None:
        call = llm.FunctionToolCall(
            name="hand_off", arguments=json.dumps({"reason": self._llm.reason}), call_id="call_1"
        )
        delta = llm.ChoiceDelta(role="assistant", tool_calls=[call])
        self._event_ch.send_nowait(llm.ChatChunk(id="1", delta=delta))


def _assistant_texts(session: AgentSession) -> list[str]:
    return [
        item.text_content
        for item in session.history.items
        if isinstance(item, llm.ChatMessage) and item.role == "assistant"
    ]


@pytest.fixture
async def session():
    fake = FakeLLM()
    async with AgentSession(llm=fake) as session:
        session.fake_llm = fake
        await session.start(ReceptionAgent())
        if session.current_speech is not None:
            await session.current_speech  # the greeting
        yield session


async def _say(session, text) -> list[str]:
    result = await session.run(user_input=text)
    return [event.item.text_content for event in result.events if event.type == "message"]


async def test_greeting_says_it_is_an_ai(session):
    assert _assistant_texts(session)[0] == texts.GREETING
    assert "künstliche Intelligenz" in texts.GREETING


async def test_ordinary_question_goes_to_the_llm(session):
    said = await _say(session, "Wann haben Sie geöffnet?")
    assert said == [FAKE_REPLY + " "]
    assert session.fake_llm.calls == 1


async def test_emergency_never_reaches_the_llm(session):
    said = await _say(session, "Mein Mann hat Brustschmerzen")
    assert "112" in said[0] and "116 117" in said[0]
    assert session.fake_llm.calls == 0


async def test_after_an_emergency_the_llm_stays_out(session):
    await _say(session, "Sie bekommt keine Luft")
    said = await _say(session, "Dann hätte ich gern einen Termin")
    assert "112" in said[0]
    assert session.fake_llm.calls == 0


async def test_health_topic_is_handed_off_without_llm(session):
    said = await _say(session, "Ich habe seit Tagen Rückenschmerzen")
    assert said == [texts.HEALTH_NOBODY]
    assert session.fake_llm.calls == 0


async def test_llm_can_trigger_the_switch():
    """What the word filter misses, the LLM hands off via `hand_off`."""
    fake = ToolCallingLLM(reason="emergency_hint")
    async with AgentSession(llm=fake) as session:
        agent = ReceptionAgent()
        await session.start(agent)
        await session.run(user_input="Meiner Oma geht es gar nicht gut")
        assert agent.gate.emergency_seen
        assert any("116 117" in text for text in _assistant_texts(session))
        await _say(session, "Wann haben Sie geöffnet?")
        assert fake.calls == 1


async def test_key_0_hands_off(session):
    handle = session.current_agent.on_dtmf("0")
    await handle
    assert _assistant_texts(session)[-1] == texts.NOBODY


async def test_key_0_cuts_the_greeting():
    """The greeting cannot be talked over, but 0 works at any moment."""
    async with AgentSession(llm=FakeLLM()) as session:
        agent = ReceptionAgent()
        await session.start(agent)
        await agent.on_dtmf("0")
        assert _assistant_texts(session)[-1] == texts.NOBODY


async def test_key_9_reads_the_privacy_notice(session):
    await session.current_agent.on_dtmf("9")
    assert _assistant_texts(session)[-1] == texts.PRIVACY_NOTICE


async def test_other_keys_do_nothing(session):
    assert session.current_agent.on_dtmf("5") is None


async def test_key_9_is_ignored_after_an_emergency(session):
    await _say(session, "Er ist bewusstlos")
    assert session.current_agent.on_dtmf("9") is None
    handle = session.current_agent.on_dtmf("0")
    await handle
    assert "112" in _assistant_texts(session)[-1]


async def test_turn_handling_stays_off_livekit_cloud():
    """Without these settings LiveKit streams caller audio to its cloud
    models for turn and interruption detection (dev mode default)."""
    session = build_session(load_settings({}))
    assert session.turn_detection == "stt"
    assert session.interruption_detection == "vad"

"""OV-024 dialogue policy and its non-interference with the call session."""

import time
from types import SimpleNamespace

import pytest

from omnivoice.config import Settings
from omnivoice.dialogue import (
    build_system_prompt,
    clarification_can_help,
    classify_turn_telemetry,
    detect_repeated_limitation,
    missing_fact_reply,
    unsupported_action_reply,
)
from omnivoice.session import CallSession
from omnivoice.transport import MediaTransport

CONFIG = {
    "language": "en-IN",
    "greeting": "Hello",
    "instructions": "Answer briefly.",
    "confirmation_phrases": ["yes confirm"],
    "backchannels": ["yeah"],
}


def test_known_fact_and_partial_knowledge_have_distinct_diagnostics():
    context = [{"title": "Campus hours", "text": "The campus opens at nine."}]
    prompt = build_system_prompt(CONFIG, context, [], ["Campus hours"], caller_text="When does campus open?")
    assert "The campus opens at nine" in prompt
    assert "say the supported part and identify the missing part once" in prompt
    assert classify_turn_telemetry("The campus opens at nine.", context)["knowledge_status"] == "grounded"
    partial = classify_turn_telemetry("The campus opens at nine. I don't have fee information.", context)
    assert partial["knowledge_status"] == "partial"
    assert partial["limitation_used"]


def test_unknown_fact_limits_once_and_does_not_invent_clarification_value():
    prompt = build_system_prompt(CONFIG, [], [], [], caller_text="How much are tuition fees?")
    assert "Clarification could improve this request: no" in prompt
    assert "Do not ask which organization, plan or program" in prompt
    assert "Do not promise transfer, callback, email, booking or escalation" in prompt
    status = classify_turn_telemetry("I don't have verified fee details on this line.", [])
    assert status == {"knowledge_status": "missing", "limitation_used": True, "clarification_requested": False}
    assert missing_fact_reply("What are the fees?", [], [], ["Campus hours"], []).endswith("I can help with Campus hours instead.")
    assert missing_fact_reply("What are the fees?", [{"title": "Fees", "text": "Verified"}], [], [], []) is None
    assert missing_fact_reply("What are the fees?", [], [{"name": "check_fees"}], [], []) is None
    assert missing_fact_reply("What are the fees?", [], [{"name": "book_slot"}], [], [])


def test_clarification_requires_two_relevant_documented_alternatives():
    options = [
        {"title": "North College fees", "text": "North College fees are listed here."},
        {"title": "South College fees", "text": "South College fees are listed here."},
    ]
    assert clarification_can_help("What are the fees?", options)
    assert not clarification_can_help("What are the fees?", [])
    assert not clarification_can_help("What are the fees?", options[:1])
    assert "Clarification could improve this request: yes" in build_system_prompt(
        CONFIG, options, [], caller_text="What are the fees?"
    )
    assert not classify_turn_telemetry("Would you like me to explain campus hours?", options)["clarification_requested"]


def test_repeated_limitation_is_only_for_related_follow_up():
    history = [
        {"role": "user", "content": "What are the tuition fees?"},
        {"role": "assistant", "content": "I don't have verified tuition fees. I can explain campus hours."},
        {"role": "user", "content": "What about tuition fees for North College?"},
    ]
    assert detect_repeated_limitation(history)
    prompt = build_system_prompt(CONFIG, [], [], ["Campus hours"], history, history[-1]["content"])
    assert "Do not repeat its wording" in prompt
    unrelated = [*history[:-1], {"role": "user", "content": "What are the campus hours?"}]
    assert not detect_repeated_limitation(unrelated)


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("Please transfer me to a human agent", "can't transfer"),
        ("Can you call me back?", "can't arrange a callback"),
        ("Can you email me the details?", "can't send an email"),
        ("Please book an appointment", "can't book an appointment"),
        ("Please open a support ticket", "can't create a support ticket"),
    ],
)
def test_unconfigured_actions_are_declined_and_redirect_only_to_available_topic(utterance, expected):
    reply = unsupported_action_reply(utterance, [], ["Campus hours"], [])
    assert expected in reply
    assert reply.endswith("I can help with Campus hours instead.")
    assert unsupported_action_reply(utterance, [], [], []) == reply.split(" I can help")[0]


def test_configured_write_action_and_information_question_are_not_blocked():
    tool = {"name": "book_slot", "description": "Book appointment", "kind": "write"}
    assert unsupported_action_reply("Please book an appointment", [tool], [], []) is None
    assert unsupported_action_reply("How do I book an appointment?", [], [], []) is None
    assert unsupported_action_reply("Please book an appointment", [{**tool, "kind": "read"}], [], [])
    assert unsupported_action_reply("Please book an appointment", [], [], [], "hi-IN") is None


class FakeTTS:
    def __init__(self, *_):
        self.spoken = []

    async def speak(self, text):
        self.spoken.append(text)
        yield b"\0" * 320

    async def cancel(self):
        pass


class FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, packet):
        self.sent.append(packet)


def make_session(fast_answer, retrieve, llm, tools=None, corpus_rows=None):
    async def confirm(*_):
        return None

    async def cancel(*_):
        pass

    async def listed_tools(*_):
        return tools or []

    knowledge = SimpleNamespace(
        fast_answer=fast_answer,
        retrieve=retrieve,
        corpora={"tenant-a": SimpleNamespace(rows=corpus_rows or [])},
    )
    services = SimpleNamespace(
        settings=Settings(_env_file=None),
        actions=SimpleNamespace(confirm=confirm, cancel=cancel, tools=listed_tools),
        knowledge=knowledge,
        llm=SimpleNamespace(stream=llm),
        vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession(
        "dialogue-call", {"id": "tenant-a", "config": CONFIG},
        MediaTransport(FakeSocket(), "exotel", "stream"), services,
    )
    session.tts = FakeTTS()
    return session


@pytest.mark.asyncio
async def test_faq_fast_path_remains_grounded_and_history_stays_bounded():
    async def fast(*_):
        return "The campus opens at nine.", "exact", 0.1

    async def should_not_run(*_):
        raise AssertionError("FAQ fast path must bypass retrieval and LLM")
        yield

    session = make_session(fast, should_not_run, should_not_run)
    for _ in range(12):
        await session.respond("When does campus open?", time.perf_counter())
    assert len(session.history) <= 20
    assert len(session.metrics["turns"]) == 12
    assert all(turn["knowledge_status"] == "grounded" for turn in session.metrics["turns"])
    assert all(not turn["limitation_used"] for turn in session.metrics["turns"])


@pytest.mark.asyncio
async def test_rag_path_keeps_grounded_answer_and_partial_limitation():
    async def miss(*_):
        return None, "miss", 0.1

    async def retrieve(*_):
        return [{"title": "Campus hours", "text": "The campus opens at nine."}]

    async def llm(messages, tools):
        assert "The campus opens at nine" in messages[0]["content"]
        assert not tools
        yield {"content": "The campus opens at nine. I don't have verified fee details."}

    session = make_session(miss, retrieve, llm)
    await session.respond("What are the hours and fees?", time.perf_counter())
    turn = session.metrics["turns"][0]
    assert turn["knowledge_status"] == "partial"
    assert turn["limitation_used"]
    assert "The campus opens at nine" in turn["agent_response"]


@pytest.mark.asyncio
async def test_missing_fact_follow_up_does_not_guess_or_repeat():
    async def miss(*_):
        return None, "miss", 0.1

    async def no_context(*_):
        return []

    async def llm(*_):
        raise AssertionError("Absent fee facts must not reach model speech")
        yield

    session = make_session(
        miss, no_context, llm,
        corpus_rows=[{"title": "Campus hours", "text": "Open at nine"}],
    )
    await session.respond("What are the tuition fees?", time.perf_counter())
    await session.respond("What about tuition fees for North College?", time.perf_counter())
    assert all(turn["knowledge_status"] == "missing" for turn in session.metrics["turns"])
    assert session.metrics["turns"][0]["agent_response"] != session.metrics["turns"][1]["agent_response"]
    assert all("Campus hours" in turn["agent_response"] for turn in session.metrics["turns"])
    assert len(session.history) == 4


@pytest.mark.asyncio
async def test_unsupported_transfer_bypasses_llm_without_affecting_action_gating():
    async def miss(*_):
        return None, "miss", 0.1

    async def no_context(*_):
        return []

    async def llm(*_):
        raise AssertionError("Unsupported transfer must not reach model speech")
        yield

    session = make_session(
        miss, no_context, llm,
        corpus_rows=[{"title": "Campus hours", "text": "Open at nine"}],
    )
    await session.respond("Please transfer me to a human agent", time.perf_counter())
    turn = session.metrics["turns"][0]
    assert turn["knowledge_status"] == "missing"
    assert "can't transfer" in turn["agent_response"]
    assert session.tts.spoken

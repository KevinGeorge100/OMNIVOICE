import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from omnivoice.actions import ActionEngine
from omnivoice.config import Settings
from omnivoice.sales import SalesService, register_sales_tools
from omnivoice.session import CallSession
from omnivoice.store import Store
from omnivoice.tools import ToolContext, ToolRegistry


@pytest.fixture
async def sales(tmp_path):
    store = Store(tmp_path / "sales.db")
    await store.open()
    a = await store.create_tenant({"name": "A", "language": "en-IN"})
    b = await store.create_tenant({"name": "B", "language": "en-IN"})
    service = SalesService(store)
    actions = ActionEngine(store, None)
    registry = ToolRegistry(store, actions)
    register_sales_tools(registry, service)
    lead_a = await service.add_lead(a["id"], "Arun", "+910000000001")
    lead_b = await service.add_lead(b["id"], "Bina", "+910000000002")
    slot_a = await service.add_slot(a["id"], "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30")
    slot_b = await service.add_slot(b["id"], "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30")
    occupied = await service.add_slot(
        a["id"], "2030-03-08T14:30:00+05:30", "2030-03-08T15:00:00+05:30", status="booked",
    )
    yield SimpleNamespace(
        store=store, service=service, actions=actions, registry=registry,
        a=a["id"], b=b["id"], lead_a=lead_a, lead_b=lead_b,
        slot_a=slot_a, slot_b=slot_b, occupied=occupied,
    )
    await store.close()


async def prepared(sales, tenant, call):
    ctx = ToolContext(tenant, call, {})
    identifier = "+910000000001" if tenant == sales.a else "+910000000002"
    assert (await sales.registry.invoke(ctx, "lookup_lead", {"identifier": identifier})).success
    assert (await sales.registry.invoke(ctx, "check_demo_slots", {
        "date": "2030-03-08", "time_preference": "afternoon",
    })).success
    return ctx


async def test_exact_lookup_and_tenant_isolation(sales):
    a = ToolContext(sales.a, "a", {})
    b = ToolContext(sales.b, "b", {})
    known = await sales.registry.invoke(a, "lookup_lead", {"identifier": "+910000000001"})
    assert known.data["lead"]["id"] == sales.lead_a
    assert "phone" not in json.dumps(known.data)
    assert (await sales.registry.invoke(b, "lookup_lead", {"identifier": "+910000000001"})).data == {
        "found": False, "reason": "not_found",
    }
    assert (await sales.registry.invoke(a, "lookup_lead", {})).data["reason"] == "identity_required"
    assert (await sales.registry.invoke(a, "lookup_lead", {"identifier": "missing"})).data["reason"] == "not_found"


async def test_slot_filter_bound_and_tenancy(sales):
    a = ToolContext(sales.a, "a", {})
    response = await sales.registry.invoke(a, "check_demo_slots", {
        "date": "2030-03-08", "time_preference": "afternoon",
    })
    assert [row["id"] for row in response.data["slots"]] == [sales.slot_a]
    assert sales.slot_b not in json.dumps(response.data)
    assert sales.occupied not in json.dumps(response.data)
    assert (await sales.registry.invoke(a, "check_demo_slots", {"date": "2030-03-09"})).data == {
        "slots": [],
    }
    for hour in range(8):
        await sales.service.add_slot(
            sales.a, f"2030-03-09T{hour + 9:02}:00:00+05:30",
            f"2030-03-09T{hour + 9:02}:30:00+05:30",
        )
    for minute in (0, 10, 20, 30, 40, 50):
        await sales.service.add_slot(
            sales.a, f"2030-03-09T17:{minute:02}:00+05:30",
            f"2030-03-09T17:{minute:02}:30+05:30",
        )
    bounded = await sales.registry.invoke(a, "check_demo_slots", {"date": "2030-03-09"})
    assert len(bounded.data["slots"]) == 8
    assert (await sales.registry.invoke(a, "check_demo_slots", {
        "date": "2030-03-08", "time_preference": "morning",
    })).data["slots"] == []
    assert (await sales.registry.invoke(a, "check_demo_slots", {
        "date": "2030-13-08",
    })).error_code == "invalid_arguments"


async def test_booking_stages_and_commits_once(sales):
    ctx = await prepared(sales, sales.a, "call-a")
    args = {"lead_id": sales.lead_a, "slot_id": sales.slot_a}
    staged = await sales.registry.invoke(ctx, "schedule_demo", args)
    assert staged.success and staged.confirmation_required
    assert "4:00 PM" in staged.safe_summary
    assert await sales.store.rows("SELECT * FROM demo_bookings") == []
    assert await sales.actions.confirm(sales.a, "call-a", "yes", True, ["yes"]) is None
    assert await sales.actions.arm(staged.data["action_id"], "call-a") == 1
    assert await sales.actions.confirm(sales.a, "call-a", "maybe", True, ["yes"]) is None
    assert await sales.actions.confirm(sales.a, "call-a", "no", True, ["yes"]) is None
    committed = await sales.actions.confirm(sales.a, "call-a", "yes", True, ["yes"])
    assert committed["status"] == "committed" and committed["result"]["ok"] is True
    assert await sales.actions.confirm(sales.a, "call-a", "yes", True, ["yes"]) is None
    assert len(await sales.store.rows("SELECT * FROM demo_bookings")) == 1
    assert (await sales.store.one("SELECT status FROM demo_slots WHERE id=?", (sales.slot_a,)))["status"] == "booked"


async def test_cross_tenant_write_and_selection_fail_closed(sales):
    ctx = await prepared(sales, sales.a, "call-a")
    for args in (
        {"lead_id": sales.lead_a, "slot_id": sales.slot_b},
        {"lead_id": sales.lead_b, "slot_id": sales.slot_a},
        {"lead_id": sales.lead_a, "slot_id": "not-an-id"},
    ):
        result = await sales.registry.invoke(ctx, "schedule_demo", args)
        assert not result.success
    assert await sales.store.rows("SELECT * FROM actions") == []
    assert await sales.store.rows("SELECT * FROM demo_bookings") == []


async def test_stale_slot_and_two_call_race(sales):
    one = await prepared(sales, sales.a, "one")
    two = await prepared(sales, sales.a, "two")
    args = {"lead_id": sales.lead_a, "slot_id": sales.slot_a}
    first = await sales.registry.invoke(one, "schedule_demo", args)
    second = await sales.registry.invoke(two, "schedule_demo", args)
    assert first.success and second.success
    await sales.actions.arm(first.data["action_id"], "one")
    await sales.actions.arm(second.data["action_id"], "two")
    results = await asyncio.gather(
        sales.actions.confirm(sales.a, "one", "yes", True, ["yes"]),
        sales.actions.confirm(sales.a, "two", "yes", True, ["yes"]),
    )
    assert sorted(item["status"] for item in results) == ["committed", "failed"]
    assert len(await sales.store.rows("SELECT * FROM demo_bookings")) == 1
    assert next(item for item in results if item["status"] == "failed")["result"]["error_code"] == "slot_unavailable"
    assert (await sales.registry.invoke(two, "schedule_demo", args)).error_code == "slot_unavailable"


async def test_followup_is_bounded_and_confirmation_gated(sales):
    ctx = await prepared(sales, sales.a, "followup")
    invalid = await sales.registry.invoke(ctx, "create_followup", {
        "lead_id": sales.lead_a, "note": "x" * 241,
    })
    assert invalid.error_code == "invalid_arguments"
    staged = await sales.registry.invoke(ctx, "create_followup", {
        "lead_id": sales.lead_a, "note": "Send brochure",
    })
    assert staged.success and await sales.store.rows("SELECT * FROM followups") == []
    await sales.actions.arm(staged.data["action_id"], "followup")
    assert (await sales.actions.confirm(sales.a, "followup", "yes", True, ["yes"]))["status"] == "committed"
    assert await sales.actions.confirm(sales.a, "followup", "yes", True, ["yes"]) is None
    assert len(await sales.store.rows("SELECT * FROM followups")) == 1


async def test_local_voice_confirmation_and_spoken_result(sales):
    ctx = await prepared(sales, sales.a, "voice")
    tenant = await sales.store.tenant(sales.a)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    responses = []

    async def stream(messages, tools):
        yield {"tool_calls": [{"index": 0, "id": "booking", "function": {
            "name": "schedule_demo", "arguments": json.dumps({
                "lead_id": sales.lead_a, "slot_id": sales.slot_a,
            }),
        }}]}

    async def fast_answer(*args):
        return None, "miss", 0

    async def retrieve(*args):
        return []

    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=sales.actions,
        tool_registry=sales.registry, llm=SimpleNamespace(stream=stream),
        knowledge=SimpleNamespace(fast_answer=fast_answer, retrieve=retrieve),
        vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("voice", tenant, None, services)
    session.sales_state.update(ctx.state)

    async def say(text, **kwargs):
        responses.append(text)
        if kwargs.get("action_id"):
            await sales.actions.arm(kwargs["action_id"], "voice")

    session.say = say
    session.say_stream = lambda *args, **kwargs: asyncio.sleep(0)
    await session.respond("Book the 4 PM slot", time.perf_counter())
    assert "Should I book" in responses[-1]
    assert await sales.store.rows("SELECT * FROM demo_bookings") == []
    await session.respond("yes", time.perf_counter())
    assert responses[-1] == "Done. Your demo is booked."
    assert len(await sales.store.rows("SELECT * FROM demo_bookings")) == 1


async def test_full_local_sales_conversation_and_repeat_confirmation(sales):
    tenant = await sales.store.tenant(sales.a)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    spoken = []
    tool_requests = []

    async def stream(messages, tools):
        if messages[-1]["role"] == "tool":
            payload = json.loads(messages[-1]["content"])
            assert payload["success"]
            if "lead" in payload["data"]:
                assert payload["data"]["lead"]["id"] == sales.lead_a
                yield {"content": "Yes, I found your lead record."}
            else:
                assert sales.slot_a in [slot["id"] for slot in payload["data"]["slots"]]
                yield {"content": "I have 4 PM available."}
            return
        user = next(message["content"] for message in reversed(messages) if message["role"] == "user")
        if "spoken" in user:
            name, args = "lookup_lead", {"identifier": "+910000000001"}
        elif "available" in user:
            name, args = "check_demo_slots", {"date": "2030-03-08", "time_preference": "afternoon"}
        elif "Book" in user:
            name, args = "schedule_demo", {"lead_id": sales.lead_a, "slot_id": sales.slot_a}
        else:
            yield {"content": "Your demo is already booked."}
            return
        tool_requests.append(name)
        yield {"tool_calls": [{"index": 0, "id": name, "function": {
            "name": name, "arguments": json.dumps(args),
        }}]}

    async def fast_answer(tenant_id, text):
        return ("We sell voice assistants.", "exact", 0) if text == "What does your product do?" else (
            None, "miss", 0,
        )

    async def retrieve(*args):
        return []

    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=sales.actions, tool_registry=sales.registry,
        llm=SimpleNamespace(stream=stream),
        knowledge=SimpleNamespace(fast_answer=fast_answer, retrieve=retrieve),
        vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("sales-smoke", tenant, None, services)

    async def say(text, **kwargs):
        spoken.append(text)
        if kwargs.get("action_id"):
            await sales.actions.arm(kwargs["action_id"], "sales-smoke")

    async def say_stream(segments, **kwargs):
        async for text in segments:
            spoken.append(text)

    session.say, session.say_stream = say, say_stream
    for utterance in (
        "What does your product do?", "Have I spoken to you? My number is +910000000001.",
        "Do you have a demo available Friday afternoon?", "Book the 4 PM slot.",
    ):
        await session.respond(utterance, time.perf_counter())
    assert tool_requests == ["lookup_lead", "check_demo_slots", "schedule_demo"]
    assert len(await sales.store.rows("SELECT * FROM demo_bookings")) == 0
    assert "Should I book" in spoken[-1]
    await session.respond("yes", time.perf_counter())
    assert spoken[-1] == "Done. Your demo is booked."
    assert len(await sales.store.rows("SELECT * FROM demo_bookings")) == 1
    await session.respond("yes", time.perf_counter())
    assert len(await sales.store.rows("SELECT * FROM demo_bookings")) == 1


async def test_evaluation_cases_are_labeled_and_metrics_are_measured():
    from scripts.evaluate_agent_tools import CASES, evaluate

    assert len(CASES) >= 20
    assert all(len(case) == 5 for case in CASES)
    result = await evaluate()
    assert result["scenario_count"] == len(CASES)
    assert all(case["task_completed"] for case in result["cases"])
    assert result["metrics"]["duplicate_execution_count"] == 0
    assert result["metrics"]["tool_selection_accuracy"] is None
    assert result["metrics"]["tool_added_response_latency_ms"] is None
    assert result["metrics"]["server_side_tool_duration_ms_mean"] >= 0


async def test_external_unknown_result_does_not_break_confirmation_voice(sales):
    tool = {
        "name": "legacy_write", "description": "Legacy write", "kind": "write",
        "parameters": {"type": "object", "properties": {"value": {"type": "string"}},
                       "required": ["value"], "additionalProperties": False},
        "confirmation_template": "Set {value}?", "url": "https://example.com/write",
    }
    await sales.store.execute("INSERT INTO tools VALUES (?,?,?)", (sales.a, "legacy_write", json.dumps(tool)))

    async def nonmapping(*args):
        return ["unexpected"]

    sales.actions.invoke = nonmapping
    staged = await sales.registry.invoke(ToolContext(sales.a, "legacy"), "legacy_write", {"value": "A"})
    await sales.actions.arm(staged.data["action_id"], "legacy")
    tenant = await sales.store.tenant(sales.a)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    session = CallSession("legacy", tenant, None, SimpleNamespace(
        settings=Settings(_env_file=None), actions=sales.actions,
        vad=SimpleNamespace(session=lambda: None),
    ))
    spoken = []

    async def say(text, **kwargs):
        spoken.append(text)

    session.say = say
    await session.respond("yes", time.perf_counter())
    assert "could not verify" in spoken[-1]
    assert session.metrics["tool_summary"]["unknown_outcome"] == 1

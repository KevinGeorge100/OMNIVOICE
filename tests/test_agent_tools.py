import asyncio
import json
import time
from types import SimpleNamespace

import pytest

from omnivoice.actions import ActionEngine
from omnivoice.config import Settings
from omnivoice.mcp_reference import server
from omnivoice.mcp_tools import MCPToolProvider
from omnivoice.session import CallSession
from omnivoice.store import Store
from omnivoice.tools import (
    ToolContext,
    ToolDefinition,
    ToolRegistry,
    register_business_profile,
)
from omnivoice.transport import MediaTransport


@pytest.fixture
async def setup(tmp_path):
    store = Store(tmp_path / "tools.db")
    await store.open()
    first = await store.create_tenant({"name": "Kerala One", "language": "ml-IN"})
    second = await store.create_tenant({"name": "Kerala Two", "language": "en-IN"})
    actions = ActionEngine(store, None)
    registry = ToolRegistry(store, actions, timeout_ms=100)
    register_business_profile(registry)
    yield store, actions, registry, first["id"], second["id"]
    await store.close()


async def test_profile_registry_is_tenant_scoped_and_fail_closed(setup):
    _, _, registry, first, second = setup
    names = [tool.name for tool in await registry.list(first)]
    assert names == ["get_business_profile"]
    assert (await registry.llm_tools(first))[0]["parameters"]["additionalProperties"] is False
    one = await registry.invoke(ToolContext(first, "call"), "get_business_profile", {})
    two = await registry.invoke(ToolContext(second, "call"), "get_business_profile", {})
    assert one.success and one.data == {"business_name": "Kerala One", "language": "ml-IN"}
    assert two.data["business_name"] == "Kerala Two"
    assert (await registry.invoke(ToolContext(first, "call"), "invented", {})).error_code == "unauthorized_tool"
    assert (await registry.invoke(ToolContext(first, "call"), "get_business_profile", {"x": 1})).error_code == "invalid_arguments"
    assert (await registry.invoke(ToolContext(first, "call"), "get_business_profile", [])).error_code == "invalid_arguments"


async def test_duplicate_output_failure_timeout_and_cancellation(setup):
    _, _, registry, first, _ = setup

    async def oversized(ctx, args):
        return {"private": "x" * 5000}

    definition = ToolDefinition(
        "oversized", "An oversized result", {"type": "object"}, "read", "local", 100,
        handler=oversized,
    )
    registry.register(definition)
    with pytest.raises(ValueError, match="Duplicate"):
        registry.register(definition)
    result = await registry.invoke(ToolContext(first, "call"), "oversized", {})
    assert result.error_code == "tool_failed" and "private" not in result.for_model()

    pending = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(ctx, args):
        pending.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    registry.register(ToolDefinition(
        "slow", "A slow read", {"type": "object"}, "read", "local", 10, handler=slow,
    ))
    timed = await registry.invoke(ToolContext(first, "call"), "slow", {})
    assert timed.error_code == "timeout" and cancelled.is_set()
    pending.clear()
    cancelled.clear()
    task = asyncio.create_task(registry.invoke(ToolContext(first, "call"), "slow", {}))
    await pending.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


async def test_write_uses_existing_action_engine_once(setup):
    store, actions, registry, first, second = setup
    tool = {
        "name": "reserve", "description": "Reserve a slot", "kind": "write",
        "parameters": {"type": "object", "properties": {"slot": {"type": "string"}},
                       "required": ["slot"], "additionalProperties": False},
        "confirmation_template": "Reserve {slot}.", "url": "https://example.com/reserve",
    }
    await store.execute(
        "INSERT INTO tools VALUES (?,?,?)", (first, "reserve", json.dumps(tool))
    )
    assert "reserve" not in [t.name for t in await registry.list(second)]
    invoked = []

    async def fake_invoke(config, arguments, action_id=None):
        invoked.append(action_id)
        return {"ok": True}

    actions.invoke = fake_invoke
    result = await registry.invoke(ToolContext(first, "call-1"), "reserve", {"slot": "A"})
    assert result.success and result.confirmation_required and result.data["state"] == "staged" and invoked == []
    action_id = result.data["action_id"]
    assert await actions.confirm(first, "call-1", "yes", True, ["yes"]) is None
    assert await actions.arm(action_id, "call-1") == 1
    assert await actions.confirm(second, "call-1", "yes", True, ["yes"]) is None
    committed = await actions.confirm(first, "call-1", "yes", True, ["yes"])
    assert committed["status"] == "committed"
    assert await actions.confirm(first, "call-1", "yes", True, ["yes"]) is None
    assert invoked == [action_id]
    row = await store.one("SELECT status,result FROM actions WHERE id=?", (action_id,))
    assert row["status"] == "committed" and json.loads(row["result"])["ok"] is True


async def test_mcp_reference_discovery_allowlist_invocation_and_shutdown(setup):
    store, actions, _, first, _ = setup
    mcp = MCPToolProvider(server, {"get_current_demo_policy", "unseen"}, 1000)
    registry = ToolRegistry(store, actions, mcp=mcp)
    assert [item.name for item in await registry.list(first)] == ["get_current_demo_policy"]
    result = await registry.invoke(ToolContext(first, "call"), "get_current_demo_policy", {})
    assert result.success and result.transport == "mcp"
    assert "no booking" in json.dumps(result.data)
    assert (await registry.invoke(ToolContext(first, "call"), "unseen", {})).error_code == "unauthorized_tool"
    await mcp.close()
    assert mcp._definitions is None


async def test_mcp_error_does_not_break_local_tools(setup):
    store, actions, _, first, _ = setup

    async def unavailable():
        raise RuntimeError("secret connection string")

    registry = ToolRegistry(store, actions, mcp=SimpleNamespace(definitions=unavailable))
    register_business_profile(registry)
    result = await registry.invoke(ToolContext(first, "call"), "get_business_profile", {})
    assert result.success


async def test_mcp_invocation_failure_is_sanitized(setup):
    store, actions, _, first, _ = setup

    async def failing(ctx, args):
        raise RuntimeError("private upstream detail")

    definition = ToolDefinition(
        "mcp_read", "Test read", {"type": "object"}, "read", "mcp", 100,
        handler=failing,
    )

    async def definitions():
        return [definition]

    registry = ToolRegistry(store, actions, mcp=SimpleNamespace(definitions=definitions))
    result = await registry.invoke(ToolContext(first, "call"), "mcp_read", {})
    assert result.error_code == "tool_failed" and "private" not in result.for_model()


@pytest.mark.parametrize("requested,arguments,expected", [
    ("get_business_profile", "{}", "Kerala One"),
    ("invented", "{}", "couldn't complete"),
    ("get_business_profile", '{"unknown":1}', "couldn't complete"),
    ("get_business_profile", "{bad", "couldn't complete"),
])
async def test_text_to_tool_to_final_voice_turn(setup, requested, arguments, expected):
    store, actions, registry, first, _ = setup
    seen = []

    async def stream(messages, tools):
        seen.append((messages, tools))
        if len(seen) == 1:
            yield {"tool_calls": [{"index": 0, "id": "call-test", "function": {
                "name": requested, "arguments": arguments,
            }}]}
        else:
            assert messages[-1]["role"] == "tool"
            assert "Kerala One" in messages[-1]["content"]
            yield {"content": "The business is Kerala One."}

    async def fast_answer(*args):
        return None, "miss", 0.1

    async def retrieve(*args):
        return []

    class TTS:
        async def speak(self, text):
            yield b"\0" * 3200

    class Socket:
        async def send_json(self, item):
            pass

    tenant = await store.tenant(first)
    tenant["config"].update({
        "greeting": "Hello", "backchannels": [], "confirmation_phrases": ["yes"],
        "instructions": "",
    })
    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=actions, tool_registry=registry,
        knowledge=SimpleNamespace(fast_answer=fast_answer, retrieve=retrieve),
        llm=SimpleNamespace(stream=stream), vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("call", tenant, MediaTransport(Socket(), "exotel", "s"), services)
    session.tts = TTS()
    await session.respond("What business is this?", time.perf_counter())
    assert expected in session.metrics["turns"][0]["agent_response"]
    assert session.metrics["turns"][0]["tool_called"] is True
    summary = session.metrics["tool_summary"]
    assert summary["invocations"] == 1
    assert summary["succeeded"] == int(expected == "Kerala One")
    assert summary["failed"] == int(expected != "Kerala One")
    assert summary["duration_ms_total"] >= 0
    assert "arguments" not in json.dumps(summary)
    assert len(seen) == (2 if requested == "get_business_profile" and arguments == "{}" else 1)


async def test_tool_loop_limit_is_deterministic(setup):
    store, actions, registry, first, _ = setup
    calls = []

    async def stream(messages, tools):
        calls.append(tools)
        yield {"tool_calls": [{"index": 0, "function": {
            "name": "get_business_profile", "arguments": "{}",
        }}]}

    tenant = await store.tenant(first)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    services = SimpleNamespace(
        settings=Settings(_env_file=None, agent_max_tool_steps=1),
        actions=actions, tool_registry=registry, llm=SimpleNamespace(stream=stream),
        vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("call", tenant, MediaTransport(SimpleNamespace(send_json=None), "exotel", "s"), services)

    async def say(text, **kwargs):
        pass

    session.say = say
    session.say_stream = lambda *args, **kwargs: asyncio.sleep(0)
    metric = {"started": time.perf_counter(), "agent_response": ""}
    await session.generate([{"role": "user", "content": "Who?"}], await registry.llm_tools(first), metric)
    assert len(calls) == 2 and calls[1] == []
    assert "couldn't complete" in metric["agent_response"]


async def test_speculation_cannot_stage_write(setup):
    store, actions, registry, first, _ = setup
    tool = {
        "name": "reserve", "description": "Reserve a slot", "kind": "write",
        "parameters": {"type": "object", "properties": {"slot": {"type": "string"}},
                       "required": ["slot"], "additionalProperties": False},
        "confirmation_template": "Reserve {slot}.", "url": "https://example.com/reserve",
    }
    await store.execute("INSERT INTO tools VALUES (?,?,?)", (first, "reserve", json.dumps(tool)))

    async def predict(*args):
        return [], [{"name": "reserve", "arguments": {"slot": "A"}}]

    async def warm(*args):
        pass

    tenant = await store.tenant(first)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=actions, tool_registry=registry,
        llm=SimpleNamespace(predict=predict), knowledge=SimpleNamespace(warm=warm),
        vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("call", tenant, None, services)
    await session.speculate("reserve a slot")
    assert await store.rows("SELECT id FROM actions WHERE tenant_id=?", (first,)) == []


async def test_foreground_reuses_bounded_speculative_read(setup):
    store, actions, registry, first, _ = setup
    requested = 0

    async def stream(messages, tools):
        nonlocal requested
        requested += 1
        if requested == 1:
            yield {"tool_calls": [{"index": 0, "id": "cached", "function": {
                "name": "get_business_profile", "arguments": "{}",
            }}]}
        else:
            assert messages[-1]["role"] == "tool"
            yield {"content": "Kerala One."}

    tenant = await store.tenant(first)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=actions, tool_registry=registry,
        llm=SimpleNamespace(stream=stream), vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("call", tenant, None, services)
    session.read_results[json.dumps(["get_business_profile", {}], sort_keys=True)] = (
        time.monotonic(), {"business_name": "Kerala One", "language": "ml-IN"},
    )

    async def unexpected_invoke(*args):
        raise AssertionError("A fresh cached read should not execute again")

    registry.invoke = unexpected_invoke
    session.say_stream = lambda *args, **kwargs: asyncio.sleep(0)
    metric = {"started": time.perf_counter(), "agent_response": ""}
    await session.generate([{"role": "user", "content": "Who?"}], await registry.llm_tools(first), metric)
    assert requested == 2
    assert session.metrics["tool_summary"]["cache_hits"] == 1
    assert session.metrics["tool_summary"]["invocations"] == 0


async def test_cancelled_read_is_counted_and_stopped(setup):
    store, actions, registry, first, _ = setup
    entered = asyncio.Event()
    exited = asyncio.Event()

    async def slow(ctx, args):
        entered.set()
        try:
            await asyncio.sleep(10)
        finally:
            exited.set()

    registry.register(ToolDefinition(
        "slow_read", "Slow read", {"type": "object", "additionalProperties": False},
        "read", "local", 5000, handler=slow,
    ))

    async def stream(messages, tools):
        yield {"tool_calls": [{"index": 0, "function": {
            "name": "slow_read", "arguments": "{}",
        }}]}

    tenant = await store.tenant(first)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=actions, tool_registry=registry,
        llm=SimpleNamespace(stream=stream), vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("call", tenant, None, services)

    async def drain(segments, **kwargs):
        async for _ in segments:
            pass

    session.say_stream = drain
    metric = {"started": time.perf_counter(), "agent_response": ""}
    task = asyncio.create_task(session.generate(
        [{"role": "user", "content": "Wait"}], await registry.llm_tools(first), metric,
    ))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert exited.is_set()
    assert session.metrics["tool_summary"]["cancelled"] == 1
    assert session.metrics["tool_summary"]["invocations"] == 1


async def test_voice_write_metrics_follow_action_confirmation(setup):
    store, actions, registry, first, _ = setup
    tool = {
        "name": "reserve", "description": "Reserve a slot", "kind": "write",
        "parameters": {"type": "object", "properties": {"slot": {"type": "string"}},
                       "required": ["slot"], "additionalProperties": False},
        "confirmation_template": "Reserve {slot}.", "url": "https://example.com/reserve",
    }
    await store.execute("INSERT INTO tools VALUES (?,?,?)", (first, "reserve", json.dumps(tool)))
    invoked = []

    async def fake_invoke(config, arguments, action_id=None):
        invoked.append(action_id)
        return {"ok": True}

    actions.invoke = fake_invoke

    async def stream(messages, tools):
        yield {"tool_calls": [{"index": 0, "function": {
            "name": "reserve", "arguments": '{"slot":"A"}',
        }}]}

    tenant = await store.tenant(first)
    tenant["config"].update({"greeting": "Hi", "backchannels": [], "confirmation_phrases": ["yes"]})
    services = SimpleNamespace(
        settings=Settings(_env_file=None), actions=actions, tool_registry=registry,
        llm=SimpleNamespace(stream=stream), vad=SimpleNamespace(session=lambda: None),
    )
    session = CallSession("call", tenant, None, services)

    async def drain(segments, **kwargs):
        async for _ in segments:
            pass

    async def say(text, **kwargs):
        pass

    session.say_stream = drain
    session.say = say
    metric = {"started": time.perf_counter(), "agent_response": ""}
    await session.generate([{"role": "user", "content": "Reserve A"}], await registry.llm_tools(first), metric)
    summary = session.metrics["tool_summary"]
    assert summary["invocations"] == 1 and summary["confirmation_required"] == 1
    assert summary["committed"] == 0 and invoked == []
    row = await store.one("SELECT id FROM actions WHERE tenant_id=? AND call_id=?", (first, "call"))
    await actions.arm(row["id"], "call")
    await session.respond("yes", time.perf_counter())
    assert summary["committed"] == 1 and invoked == [row["id"]]
    assert await actions.confirm(first, "call", "yes", True, ["yes"]) is None

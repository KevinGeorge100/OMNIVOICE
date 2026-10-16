"""Tenant-scoped agent capabilities above the existing action lifecycle."""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Literal

from jsonschema import Draft202012Validator, ValidationError

MAX_ARGUMENT_BYTES = 4096
MAX_RESULT_BYTES = 4096
ReadHandler = Callable[["ToolContext", dict], Awaitable[object]]


@dataclass(frozen=True)
class ToolContext:
    tenant_id: str
    call_id: str


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict
    kind: Literal["read", "write"]
    transport: Literal["local", "https", "mcp"]
    timeout_ms: int
    handler: ReadHandler | None = None
    output_schema: dict | None = None
    confirmation_required: bool = False

    def __post_init__(self):
        if not self.name or not self.description or self.timeout_ms < 1:
            raise ValueError("Invalid tool definition")
        if self.kind == "write" and (self.handler is not None or not self.confirmation_required):
            raise ValueError("Writes must use ActionEngine confirmation")
        if self.kind == "read" and self.handler is None:
            raise ValueError("Read tool requires an explicit handler")
        Draft202012Validator.check_schema(self.input_schema)
        if self.input_schema.get("type") != "object":
            raise ValueError("Tool input must be an object schema")
        if self.output_schema is not None:
            Draft202012Validator.check_schema(self.output_schema)

    def llm_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
            "kind": self.kind,
        }


@dataclass(frozen=True)
class ToolResult:
    success: bool
    tool_name: str
    data: object | None = None
    safe_summary: str = ""
    error_code: str | None = None
    retryable: bool = False
    transport: str = "local"
    duration_ms: float = 0.0
    confirmation_required: bool = False

    def for_model(self) -> str:
        return json.dumps(
            {
                "success": self.success,
                "data": self.data,
                "error_code": self.error_code,
                "safe_summary": self.safe_summary,
            },
            ensure_ascii=False,
        )


class ToolRegistry:
    def __init__(self, store, actions, *, timeout_ms=3000, events=None, mcp=None):
        self.store, self.actions = store, actions
        self.timeout_ms, self.events, self.mcp = timeout_ms, events, mcp
        self._local: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition):
        if definition.name in self._local:
            raise ValueError("Duplicate tool name")
        self._local[definition.name] = definition

    def reserved_names(self) -> set[str]:
        return set(self._local) | (set(self.mcp.allowed_tools) if self.mcp else set())

    async def _definitions(self, tenant_id: str) -> dict[str, ToolDefinition]:
        definitions = dict(self._local)
        for item in await self.actions.tools(tenant_id):
            name = item["name"]
            if name in definitions:
                raise ValueError("Duplicate tool name")

            async def read(ctx, args, tool_name=name):
                return await self.actions.read(ctx.tenant_id, tool_name, args)

            definitions[name] = ToolDefinition(
                name=name, description=item["description"], input_schema=item["parameters"],
                kind=item["kind"], transport="https", timeout_ms=self.timeout_ms,
                handler=read if item["kind"] == "read" else None,
                confirmation_required=item["kind"] == "write",
            )
        if self.mcp:
            try:
                mcp_definitions = await self.mcp.definitions()
            except (Exception, TimeoutError):
                mcp_definitions = []
            for item in mcp_definitions:
                if item.name in definitions:
                    raise ValueError("Duplicate tool name")
                definitions[item.name] = item
        return definitions

    async def list(self, tenant_id: str) -> list[ToolDefinition]:
        return list((await self._definitions(tenant_id)).values())

    async def llm_tools(self, tenant_id: str) -> list[dict]:
        return [item.llm_schema() for item in await self.list(tenant_id)]

    async def resolve(self, tenant_id: str, name: str) -> ToolDefinition:
        definition = (await self._definitions(tenant_id)).get(name)
        if definition is None:
            raise ValueError("Tool is not authorized for this tenant")
        return definition

    def _event(self, ctx, name, event, kind, transport, **fields):
        if self.events:
            with contextlib.suppress(Exception):
                self.events.publish(
                    ctx.tenant_id, event,
                    {"tool_name": name, "tenant_id": ctx.tenant_id, "call_id": ctx.call_id,
                     "kind": kind, "transport": transport, **fields},
                )

    async def invoke(self, ctx: ToolContext, name: str, arguments: object) -> ToolResult:
        started = time.perf_counter()
        try:
            definition = await self.resolve(ctx.tenant_id, name)
        except (ValueError, KeyError):
            return ToolResult(False, name, error_code="unauthorized_tool", safe_summary="That tool is unavailable.")
        self._event(ctx, name, "tool.requested", definition.kind, definition.transport)
        try:
            if not isinstance(arguments, dict) or len(json.dumps(arguments).encode()) > MAX_ARGUMENT_BYTES:
                raise ValidationError("Arguments must be a bounded object")
            Draft202012Validator(definition.input_schema).validate(arguments)
            if definition.kind == "write":
                staged = await self.actions.stage(ctx.tenant_id, ctx.call_id, name, arguments)
                self._event(ctx, name, "tool.confirmation_required", definition.kind, definition.transport)
                return ToolResult(
                    True, name, data={"action_id": staged["id"], "state": "staged"},
                    safe_summary=staged["summary"], transport=definition.transport,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    confirmation_required=True,
                )
            self._event(ctx, name, "tool.started", definition.kind, definition.transport)
            async with asyncio.timeout(definition.timeout_ms / 1000):
                data = await definition.handler(ctx, arguments)
            serialized = json.dumps(data, ensure_ascii=False)
            if len(serialized.encode()) > MAX_RESULT_BYTES:
                raise ValueError("Tool result too large")
            if definition.output_schema is not None:
                Draft202012Validator(definition.output_schema).validate(data)
            result = ToolResult(
                True, name, data=data, transport=definition.transport,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            self._event(ctx, name, "tool.succeeded", definition.kind, definition.transport,
                        duration_ms=result.duration_ms, result_status="ok")
            return result
        except asyncio.CancelledError:
            self._event(ctx, name, "tool.failed", definition.kind, definition.transport,
                        error_category="cancelled")
            raise
        except Exception as error:
            code = (
                "invalid_arguments" if isinstance(error, ValidationError) else
                "timeout" if isinstance(error, TimeoutError) else "tool_failed"
            )
            result = ToolResult(
                False, name, error_code=code, retryable=code == "timeout",
                safe_summary="That tool could not be completed.", transport=definition.transport,
                duration_ms=(time.perf_counter() - started) * 1000,
            )
            self._event(ctx, name, "tool.failed", definition.kind, definition.transport,
                        duration_ms=result.duration_ms, error_category=code)
            return result


async def get_business_profile(ctx: ToolContext, arguments: dict, store) -> dict:
    tenant = await store.tenant(ctx.tenant_id)
    if tenant is None:
        raise ValueError("Tenant unavailable")
    return {"business_name": tenant["name"], "language": tenant["config"].get("language", "en-IN")}


def register_business_profile(registry: ToolRegistry):
    async def read(ctx, arguments):
        return await get_business_profile(ctx, arguments, registry.store)

    registry.register(ToolDefinition(
        name="get_business_profile",
        description="Read this line's verified business name and language.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        output_schema={"type": "object", "required": ["business_name", "language"],
                       "properties": {"business_name": {"type": "string"},
                                      "language": {"type": "string"}},
                       "additionalProperties": False},
        kind="read", transport="local", timeout_ms=registry.timeout_ms, handler=read,
    ))

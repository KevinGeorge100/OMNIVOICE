"""Official MCP SDK adapter; discovery alone never grants capability."""

import asyncio
import json

from .tools import MAX_RESULT_BYTES, ToolDefinition


class MCPToolProvider:
    def __init__(self, server, allowed_tools: set[str], timeout_ms: int):
        self.server = server
        self.allowed_tools = frozenset(allowed_tools)
        self.timeout_ms = timeout_ms
        self._definitions = None

    async def definitions(self) -> list[ToolDefinition]:
        if self._definitions is not None:
            return self._definitions
        from mcp import Client

        async with asyncio.timeout(self.timeout_ms / 1000):
            async with Client(self.server) as client:
                found = []
                cursor = None
                while True:
                    page = await client.list_tools(cursor=cursor)
                    found.extend(page.tools)
                    cursor = page.next_cursor
                    if not cursor or len(found) > 64:
                        break
        definitions = []
        seen = set()
        for tool in found:
            if tool.name not in self.allowed_tools:
                continue
            if tool.name in seen:
                raise ValueError("Duplicate MCP tool name")
            seen.add(tool.name)
            if not tool.annotations or tool.annotations.read_only_hint is not True:
                continue
            schema = tool.input_schema
            if not isinstance(schema, dict) or schema.get("type") != "object":
                continue

            async def read(ctx, arguments, name=tool.name):
                return await self.invoke(name, arguments)

            definitions.append(ToolDefinition(
                name=tool.name, description=(tool.description or tool.name)[:240],
                input_schema=schema, output_schema=tool.output_schema,
                kind="read", transport="mcp", timeout_ms=self.timeout_ms, handler=read,
            ))
        self._definitions = definitions
        return definitions

    async def invoke(self, name: str, arguments: dict):
        if name not in self.allowed_tools or self._definitions is None or not any(
            item.name == name for item in self._definitions
        ):
            raise ValueError("MCP tool is not authorized")
        from mcp import Client

        async with asyncio.timeout(self.timeout_ms / 1000):
            async with Client(self.server) as client:
                result = await client.call_tool(name, arguments)
        if result.is_error:
            raise ValueError("MCP tool failed")
        data = result.structured_content
        if data is None:
            texts = [block.text for block in result.content if getattr(block, "type", None) == "text"]
            data = {"content": texts}
        if len(json.dumps(data, ensure_ascii=False).encode()) > MAX_RESULT_BYTES:
            raise ValueError("MCP result too large")
        return data

    async def close(self):
        self._definitions = None

"""Small deterministic MCP reference server; no tenant data or writes."""

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

server = MCPServer("OmniVoice reference")


@server.tool(
    description="State what the reference server can safely demonstrate.",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False),
)
def get_current_demo_policy() -> dict[str, str]:
    return {"policy": "Reference read-only integration; no booking or CRM capability."}

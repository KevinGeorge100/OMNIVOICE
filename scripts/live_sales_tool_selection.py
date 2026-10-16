"""Optional, low-volume Groq tool-selection smoke with synthetic tenant data."""

import asyncio
import json
import tempfile
from pathlib import Path

import httpx

from omnivoice.actions import ActionEngine
from omnivoice.config import Settings
from omnivoice.dialogue import build_system_prompt
from omnivoice.providers import Groq
from omnivoice.sales import SalesService, register_sales_tools
from omnivoice.store import Store
from omnivoice.tools import ToolRegistry


async def main():
    settings = Settings()
    if not settings.groq_api_key.get_secret_value():
        print(json.dumps({"status": "skipped", "reason": "Groq key not configured"}))
        return
    with tempfile.TemporaryDirectory() as directory:
        store = Store(Path(directory) / "live-smoke.db")
        await store.open()
        try:
            tenant = await store.create_tenant({"name": "Synthetic Sales Demo", "language": "en-IN"})
            sales = SalesService(store)
            lead_id = await sales.add_lead(tenant["id"], "Arun", "DEMO-ARUN-001")
            slot_id = await sales.add_slot(
                tenant["id"], "2030-03-08T16:00:00+05:30", "2030-03-08T16:30:00+05:30",
            )
            async with httpx.AsyncClient(trust_env=False) as http:
                registry = ToolRegistry(store, ActionEngine(store, http))
                register_sales_tools(registry, sales)
                llm = Groq(settings, http)
                tools = await registry.llm_tools(tenant["id"])
                cases = [
                    ("Have I spoken to you? My identifier is DEMO-ARUN-001.", "lookup_lead", {}),
                    ("Do you have demo slots on 2030-03-08 afternoon?", "check_demo_slots", {}),
                    ("Book the 4 PM demo we discussed.", "schedule_demo", {
                        "lead_id": lead_id, "lead_name": "Arun", "offered_slots": [slot_id],
                        "offered_slot_details": [{"id": slot_id, "start_at": "2030-03-08T16:00:00+05:30",
                                                  "end_at": "2030-03-08T16:30:00+05:30"}],
                    }),
                ]
                results = []
                for utterance, expected, state in cases:
                    prompt = build_system_prompt(
                        config={"language": "en-IN", "instructions": "Offer sales demos."},
                        context=[], tools=tools, caller_text=utterance, sales_state=state,
                    )
                    calls = {}
                    content = []
                    async for delta in llm.stream(
                        [{"role": "system", "content": prompt},
                         {"role": "user", "content": utterance}], tools,
                    ):
                        content.append(delta.get("content") or "")
                        for item in delta.get("tool_calls", []):
                            entry = calls.setdefault(item["index"], "")
                            calls[item["index"]] = entry + item.get("function", {}).get("name", "")
                    selected = list(calls.values())
                    results.append({"expected": expected, "selected": selected,
                                    "matched": selected == [expected],
                                    "response": "".join(content)[:300]})
                print(json.dumps({"status": "completed", "provider": "Groq", "cases": results}))
        finally:
            await store.close()


if __name__ == "__main__":
    asyncio.run(main())

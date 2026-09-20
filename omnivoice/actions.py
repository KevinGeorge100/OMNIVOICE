import asyncio
import ipaddress
import json
import os
import socket
import time
from string import Formatter
from urllib.parse import urlsplit
from uuid import uuid4

from dotenv import dotenv_values
from jsonschema import Draft202012Validator

from .duplex import normalize


async def validate_public_url(url: str):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise ValueError("Tool endpoints must use HTTPS on port 443 without embedded credentials")
    addresses = await asyncio.to_thread(socket.getaddrinfo, parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(entry[4][0]).is_global for entry in addresses):
        raise ValueError("Tool endpoints must resolve exclusively to public addresses")
    return parsed, addresses[0][4][0]


def validate_tool(config):
    Draft202012Validator.check_schema(config["parameters"])
    if config["parameters"].get("type") != "object":
        raise ValueError("Tool parameters must be an object schema")

    def validate_refs(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "$ref" and not str(item).startswith("#/"):
                    raise ValueError("Only local JSON schema references are allowed")
                validate_refs(item)
        elif isinstance(value, list):
            for item in value:
                validate_refs(item)

    validate_refs(config["parameters"])
    if config["kind"] == "write":
        template = config["confirmation_template"]
        if not template:
            raise ValueError("Write tools require a confirmation template")
        fields = {name for _, name, _, _ in Formatter().parse(template) if name}
        properties = set(config["parameters"].get("properties", {}))
        if config["parameters"].get("additionalProperties") is not False:
            raise ValueError("Write tools must forbid additional properties")
        if set(config["parameters"].get("required", [])) != properties:
            raise ValueError("All write arguments must be required and disclosed")
        if not fields.issubset(properties) or not properties.issubset(fields):
            raise ValueError(
                "The confirmation template must name every parameter, using simple {field} placeholders"
            )


class ActionEngine:
    def __init__(self, store, http):
        self.store, self.http = store, http
        self.tasks = set()
        self.secrets = {**dotenv_values(".env"), **os.environ}

    async def tools(self, tenant_id):
        rows = await self.store.rows("SELECT config FROM tools WHERE tenant_id=?", (tenant_id,))
        return [json.loads(row["config"]) for row in rows]

    async def get_tool(self, tenant_id, name):
        row = await self.store.one("SELECT config FROM tools WHERE tenant_id=? AND name=?", (tenant_id, name))
        if not row:
            raise ValueError("Tool is not registered for this tenant")
        return json.loads(row["config"])

    async def read(self, tenant_id, name, arguments):
        tool = await self.get_tool(tenant_id, name)
        if tool["kind"] != "read":
            raise ValueError("Speculation may only execute read tools")
        Draft202012Validator(tool["parameters"]).validate(arguments)
        return await self.invoke(tool, arguments)

    async def invoke(self, tool, arguments, action_id=None):
        parsed, address = await validate_public_url(tool["url"])
        headers = {"Idempotency-Key": action_id} if action_id else {}
        if name := tool.get("auth_env"):
            secret = self.secrets.get(name)
            if not secret:
                raise ValueError("Connector authentication is not configured")
            headers["Authorization"] = "Bearer " + secret
        # Pin the validated public address to avoid a second DNS lookup/rebinding.
        netloc = "[" + address + "]" if ":" in address else address
        target = parsed._replace(netloc=netloc).geturl()
        headers["Host"] = parsed.hostname
        # These are async tool I/O off the audio path. No automatic write retries.
        async with self.http.stream(
            "POST",
            target,
            json=arguments,
            headers=headers,
            timeout=8,
            extensions={"sni_hostname": parsed.hostname},
        ) as response:
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 32768:
                    raise ValueError("Tool response exceeds 32 KiB")
            return json.loads(data)

    async def stage(self, tenant_id, call_id, name, arguments):
        tool = await self.get_tool(tenant_id, name)
        if tool["kind"] != "write":
            raise ValueError("Only write tools can be staged")
        Draft202012Validator(tool["parameters"]).validate(arguments)
        summary = tool["confirmation_template"].format_map(arguments)
        await self.cancel(call_id)
        action_id = uuid4().hex
        now = time.time()
        await self.store.execute(
            "INSERT INTO actions VALUES (?,?,?,?,?,?,?,?,?,?,NULL)",
            (
                action_id,
                tenant_id,
                call_id,
                name,
                json.dumps(arguments),
                json.dumps(tool),
                summary,
                "staged",
                now,
                now + 120,
            ),
        )
        return {"id": action_id, "summary": summary}

    async def arm(self, action_id, call_id):
        return await self.store.execute(
            "UPDATE actions SET status='armed' WHERE id=? AND call_id=? AND status='staged' AND expires>?",
            (action_id, call_id, time.time()),
        )

    async def cancel(self, call_id):
        await self.store.execute(
            "UPDATE actions SET status='cancelled' WHERE call_id=? AND status IN ('staged','armed')",
            (call_id,),
        )

    async def confirm(self, tenant_id, call_id, text, final, phrases):
        if not final or normalize(text) not in {normalize(p) for p in phrases}:
            return None
        row = await self.store.one(
            "SELECT * FROM actions WHERE tenant_id=? AND call_id=? AND status='armed' AND expires>?",
            (tenant_id, call_id, time.time()),
        )
        if not row:
            return None
        claimed = await self.store.execute(
            "UPDATE actions SET status='executing' WHERE id=? AND status='armed'", (row["id"],)
        )
        if not claimed:
            return None
        task = asyncio.create_task(self._commit(row))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        # Call interruption cannot turn a possibly executed write back into a staged action.
        return await asyncio.shield(task)

    async def _commit(self, row):
        try:
            tool = json.loads(row["tool_config"])
            result = await self.invoke(tool, json.loads(row["arguments"]), row["id"])
            status = "committed" if isinstance(result, dict) and result.get("ok") is True else "unknown"
        except Exception:
            result, status = (
                {"message": "External outcome uncertain; manual reconciliation required. Do not retry."},
                "unknown",
            )
        await self.store.execute(
            "UPDATE actions SET status=?,result=? WHERE id=?", (status, json.dumps(result), row["id"])
        )
        return {"status": status, "result": result}

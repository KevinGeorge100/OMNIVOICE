import asyncio
import hashlib
import json
import secrets
import time
from pathlib import Path
from uuid import uuid4

import aiosqlite


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS tenants (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
 config TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS knowledge (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 kind TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL,
 approved INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE INDEX IF NOT EXISTS knowledge_tenant ON knowledge(tenant_id);
CREATE TABLE IF NOT EXISTS lines (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 provider TEXT NOT NULL, number TEXT NOT NULL UNIQUE, stream_secret TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tools (
 tenant_id TEXT NOT NULL REFERENCES tenants(id), name TEXT NOT NULL,
 config TEXT NOT NULL, PRIMARY KEY(tenant_id,name));
CREATE TABLE IF NOT EXISTS calls (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id),
 provider TEXT NOT NULL, status TEXT NOT NULL, started REAL NOT NULL,
 ended REAL, metrics TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS calls_tenant ON calls(tenant_id, started);
CREATE TABLE IF NOT EXISTS actions (
 id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL REFERENCES tenants(id), call_id TEXT NOT NULL,
 tool TEXT NOT NULL, arguments TEXT NOT NULL, tool_config TEXT NOT NULL, summary TEXT NOT NULL,
 status TEXT NOT NULL, created REAL NOT NULL, expires REAL NOT NULL, result TEXT);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.lock = asyncio.Lock()

    async def open(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        # A crashed worker cannot safely assume an external write did or did not happen.
        await self.db.execute("UPDATE actions SET status='unknown' WHERE status='executing'")
        await self.db.execute("UPDATE actions SET status='cancelled' WHERE status IN ('staged','armed')")
        await self.db.execute(
            "UPDATE calls SET status='interrupted', ended=? WHERE ended IS NULL", (time.time(),)
        )
        await self.db.commit()

    async def close(self):
        await self.db.close()

    async def rows(self, sql, args=()):
        async with self.lock:
            async with self.db.execute(sql, args) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def one(self, sql, args=()):
        rows = await self.rows(sql, args)
        return rows[0] if rows else None

    async def execute(self, sql, args=()):
        async with self.lock:
            cursor = await self.db.execute(sql, args)
            await self.db.commit()
            return cursor.rowcount

    async def create_tenant(self, config: dict):
        tenant_id, token = uuid4().hex, secrets.token_urlsafe(32)
        await self.execute(
            "INSERT INTO tenants VALUES (?,?,?,?,0,?)",
            (
                tenant_id,
                config["name"],
                token_hash(token),
                json.dumps(config, ensure_ascii=False),
                time.time(),
            ),
        )
        return {"id": tenant_id, "name": config["name"], "api_token": token}

    async def tenant(self, tenant_id):
        row = await self.one("SELECT * FROM tenants WHERE id=?", (tenant_id,))
        if row:
            row["config"] = json.loads(row["config"])
            row.pop("token_hash")
        return row

    async def add_knowledge(self, tenant_id, kind, title, content, approved=False):
        item_id = uuid4().hex
        async with self.lock:
            await self.db.execute(
                "INSERT INTO knowledge VALUES (?,?,?,?,?,?,?)",
                (item_id, tenant_id, kind, title, content, int(approved), time.time()),
            )
            await self.db.execute("UPDATE tenants SET revision=revision+1 WHERE id=?", (tenant_id,))
            await self.db.commit()
        return item_id

    async def delete_knowledge(self, tenant_id, item_id):
        async with self.lock:
            cursor = await self.db.execute(
                "DELETE FROM knowledge WHERE id=? AND tenant_id=?", (item_id, tenant_id)
            )
            await self.db.execute("UPDATE tenants SET revision=revision+1 WHERE id=?", (tenant_id,))
            await self.db.commit()
            return cursor.rowcount

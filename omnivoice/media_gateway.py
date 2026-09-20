"""Development tunnel ingress: only authenticated Exotel media, never console APIs."""

import asyncio
import logging
import re
import secrets

import aiosqlite
from fastapi import FastAPI, WebSocket
from websockets.asyncio.client import connect

from .config import Settings

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


@app.websocket("/ws/exotel/{line_id}/{token}")
async def media(ws: WebSocket, line_id: str, token: str):
    if not re.fullmatch(r"[a-f0-9]{32}", line_id) or len(token) > 128:
        await ws.close(1008)
        return
    async with aiosqlite.connect(Settings().database) as db:
        async with db.execute(
            "SELECT stream_secret FROM lines WHERE id=? AND provider='exotel'", (line_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row or not secrets.compare_digest(token, row[0]):
        await ws.close(1008)
        return
    tasks = []
    try:
        async with connect(
            f"ws://127.0.0.1:8000/ws/exotel/{line_id}/{token}",
            max_size=65536, max_queue=16, open_timeout=5, proxy=None,
        ) as upstream:
            await ws.accept()

            async def caller_to_core():
                while True:
                    message = await ws.receive()
                    if message["type"] == "websocket.disconnect":
                        logging.getLogger("omnivoice.gateway").warning(
                            "Carrier disconnected code=%s reason=%s", message.get("code"),
                            str(message.get("reason", ""))[:240],
                        )
                        return
                    await upstream.send(message.get("text") or message.get("bytes", b""))

            async def core_to_caller():
                async for message in upstream:
                    if isinstance(message, str):
                        await ws.send_text(message)
                    else:
                        await ws.send_bytes(message)

            tasks = [asyncio.create_task(caller_to_core()), asyncio.create_task(core_to_caller())]
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except Exception as error:
        # Never log URLs: they contain the routing credential.
        logging.getLogger("omnivoice.gateway").warning("Gateway ended: %s", type(error).__name__)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await ws.close()
        except Exception:
            pass

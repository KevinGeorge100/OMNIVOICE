"""Single-worker, tenant-scoped console events; no audio or provider secrets."""

import asyncio
from collections import defaultdict


class TenantEvents:
    def __init__(self):
        self.listeners = defaultdict(set)

    def subscribe(self, tenant_id):
        queue = asyncio.Queue(maxsize=32)
        self.listeners[tenant_id].add(queue)
        return queue

    def unsubscribe(self, tenant_id, queue):
        listeners = self.listeners.get(tenant_id)
        if listeners is not None:
            listeners.discard(queue)
            if not listeners:
                self.listeners.pop(tenant_id, None)

    def publish(self, tenant_id, kind, call):
        event = {"type": kind, "call": call}
        for queue in tuple(self.listeners.get(tenant_id, ())):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

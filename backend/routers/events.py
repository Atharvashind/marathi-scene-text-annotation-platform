import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/events", tags=["events"])

# Simple in-process event bus: list of queues
_subscribers: list[asyncio.Queue] = []


def publish_event(event_type: str, data: dict) -> None:
    """Publish an SSE event to all connected clients."""
    payload = {"type": event_type, **data}
    for q in _subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass  # drop event for slow consumers


async def _event_stream(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                yield ": heartbeat\n\n"  # keep-alive comment
    finally:
        if queue in _subscribers:
            _subscribers.remove(queue)


@router.get("")
async def sse_stream():
    """Server-Sent Events stream for real-time status updates."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(queue)
    return StreamingResponse(
        _event_stream(queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

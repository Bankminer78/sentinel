"""Real-time event streaming via Server-Sent Events."""
import asyncio, json, time

_listeners: list[asyncio.Queue] = []


async def emit_event(event_type: str, data: dict):
    """Broadcast event to all subscribed listeners."""
    payload = {"type": event_type, "data": data, "ts": time.time()}
    for q in list(_listeners):
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            pass


def subscribe() -> asyncio.Queue:
    """Add a new listener — returns its queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _listeners.append(q)
    return q


def unsubscribe(queue: asyncio.Queue):
    """Remove a listener queue if present."""
    if queue in _listeners:
        _listeners.remove(queue)


def listener_count() -> int:
    return len(_listeners)


def clear_listeners():
    _listeners.clear()


def format_sse(payload: dict) -> str:
    """Format a payload as an SSE data frame."""
    return f"event: {payload.get('type', 'message')}\ndata: {json.dumps(payload)}\n\n"


async def event_stream(queue: asyncio.Queue):
    """Async generator yielding SSE-formatted strings."""
    try:
        while True:
            payload = await queue.get()
            yield format_sse(payload)
    finally:
        unsubscribe(queue)

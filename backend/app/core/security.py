from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import perf_counter

from fastapi import Request, Response


SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


async def security_headers_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    started = perf_counter()
    response = await call_next(request)
    elapsed_ms = int((perf_counter() - started) * 1000)
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    if request.url.path.startswith("/api/"):
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
    return response

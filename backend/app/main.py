from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.errors import AppError, app_error_handler, validation_error_handler
from app.core.security import security_headers_middleware
from app.services.session_store import session_store


async def session_cleanup_loop() -> None:
    while True:
        await asyncio.sleep(60)
        await session_store.cleanup_expired()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    cleanup_task = asyncio.create_task(session_cleanup_loop())
    try:
        yield
    finally:
        cleanup_task.cancel()
        await session_store.close_all()


app = FastAPI(title="Local Mail Demo", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "127.0.0.1",
        "localhost",
        "127.0.0.1:8000",
        "localhost:8000",
        "127.0.0.1:8765",
        "localhost:8765",
        "testserver",
    ],
)
app.middleware("http")(security_headers_middleware)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.include_router(router)

DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if (DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
async def spa_fallback(path: str) -> FileResponse:
    if path.startswith("api/"):
        raise AppError(404, "NOT_FOUND", "接口不存在。")
    index = DIST_DIR / "index.html"
    if not index.exists():
        raise AppError(404, "NOT_FOUND", "前端构建产物不存在，请先运行 npm run build。")
    return FileResponse(index, headers={"Cache-Control": "no-store"})

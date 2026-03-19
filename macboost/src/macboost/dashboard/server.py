"""FastAPI server para el dashboard web."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from macboost.dashboard.api import router as api_router
from macboost.dashboard.websocket import websocket_endpoint

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="MacBoost Dashboard", version="1.0.0")
app.include_router(api_router)
app.add_api_websocket_route("/ws/metrics", websocket_endpoint)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "MacBoost Dashboard API", "docs": "/docs"}


def start_server(host: str = "127.0.0.1", port: int = 7777):
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    start_server()

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .api.routes import router

app = FastAPI(
    title="GitHub Issue Code Analyzer",
    description="Analyze GitHub Issues and locate relevant code with fix suggestions",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    if index_path.exists():
        return index_path.read_text(encoding="utf-8")
    return "<h1>Frontend not found</h1>"


@app.get("/health")
async def health():
    return {"status": "ok"}

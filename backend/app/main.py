from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

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

# ── 前端挂载：部署模式优先，开发模式兜底 ──
dist_path = Path(__file__).parent.parent.parent / "frontend" / "dist"

if dist_path.exists():
    # 部署模式：挂载 dist/assets/ 静态资源，返回 dist/index.html
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")


@app.get("/", response_class=HTMLResponse)
async def index():
    # 部署模式 → dist/index.html；开发模式 → frontend/index.html
    if dist_path.exists():
        dist_index = dist_path / "index.html"
        if dist_index.exists():
            return dist_index.read_text(encoding="utf-8")
    dev_index = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    if dev_index.exists():
        return dev_index.read_text(encoding="utf-8")
    return "<h1>Frontend not found</h1>"


@app.get("/health")
async def health():
    return {"status": "ok"}

from __future__ import annotations

import pathlib
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import analyze, compare, ai, admin

app = FastAPI(
    title="태양광 설계 자동화 API",
    description="주소 입력 → 건축물대장·일사량 수집 → 설계 → 보고서 생성",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(compare.router)
app.include_router(ai.router)
app.include_router(admin.router)

_REPORTS_DIR = pathlib.Path(__file__).parent.parent / "output" / "reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(_REPORTS_DIR)), name="files")


@app.get("/health")
def health():
    return {"status": "ok"}


# ── 프론트엔드 정적 파일 서빙 (빌드된 경우에만) ──────────────────────────────
_FRONTEND_DIST = pathlib.Path(__file__).parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    # Vite 빌드 결과물의 /assets 디렉터리 (JS·CSS·이미지)
    _assets_dir = _FRONTEND_DIST / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="vite-assets")

    # SPA 라우팅 폴백: 위에서 처리되지 않은 모든 경로 → index.html
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index))


if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)

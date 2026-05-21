"""관리자 기준 입력 API."""
from __future__ import annotations
import base64
import json
import os
import pathlib
import requests as _req
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["admin"])

_PASSWORD    = "solar1234"
_CONFIG_FILE = pathlib.Path(__file__).parent.parent.parent / "admin_config.json"

_GH_REPO = "songeunki/solar-design"
_GH_PATH = "data/analysis_log.json"
_GH_API  = f"https://api.github.com/repos/{_GH_REPO}/contents/{_GH_PATH}"

_DEFAULTS: dict = {
    "panel_watt":       640,
    "panel_efficiency": 0.20,
    "system_loss":      0.14,
    "panel_width_m":    1.134,
    "panel_height_m":   2.094,
    "revenue_per_kwh":  150,
    "cost_per_kw":      150,
}


def _load() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return {**_DEFAULTS, **json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(_DEFAULTS)


def _check(password: str) -> None:
    if password != _PASSWORD:
        raise HTTPException(status_code=401, detail="비밀번호가 올바르지 않습니다.")


# ── GET ───────────────────────────────────────────────────────────────────────

@router.get("/api/admin/config")
async def get_config(password: str):
    _check(password)
    return _load()


# ── POST ──────────────────────────────────────────────────────────────────────

class AdminConfigBody(BaseModel):
    password:         str
    panel_watt:       float | None = None
    panel_efficiency: float | None = None   # 소수 (0.20 = 20%)
    system_loss:      float | None = None   # 소수 (0.14 = 14%)
    panel_width_m:    float | None = None
    panel_height_m:   float | None = None
    revenue_per_kwh:  float | None = None
    cost_per_kw:      float | None = None   # 만원/kW


@router.get("/api/admin/logs")
async def get_logs(password: str):
    _check(password)
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN 미설정")
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }
    try:
        r = _req.get(_GH_API, headers=headers, timeout=10)
        if r.status_code == 404:
            return {"total_count": 0, "logs": []}
        r.raise_for_status()
        content = base64.b64decode(r.json()["content"]).decode("utf-8")
        logs = json.loads(content)
        logs_sorted = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"total_count": len(logs_sorted), "logs": logs_sorted}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GitHub 로그 조회 실패: {e}")


@router.post("/api/admin/config")
async def save_config(body: AdminConfigBody):
    _check(body.password)

    updates = {
        k: v for k, v in {
            "panel_watt":       body.panel_watt,
            "panel_efficiency": body.panel_efficiency,
            "system_loss":      body.system_loss,
            "panel_width_m":    body.panel_width_m,
            "panel_height_m":   body.panel_height_m,
            "revenue_per_kwh":  body.revenue_per_kwh,
            "cost_per_kw":      body.cost_per_kw,
        }.items() if v is not None
    }

    new_cfg = {**_load(), **updates}
    _CONFIG_FILE.write_text(
        json.dumps(new_cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"ok": True, "config": new_cfg}

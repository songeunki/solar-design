"""관리자 기준 입력 API."""
from __future__ import annotations
import json
import pathlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["admin"])

_PASSWORD    = "solar1234"
_CONFIG_FILE = pathlib.Path(__file__).parent.parent.parent / "admin_config.json"
_LOG_FILE    = pathlib.Path(__file__).parent.parent.parent / "analysis_log.json"

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
    if not _LOG_FILE.exists():
        return {"total_count": 0, "logs": []}
    try:
        logs = json.loads(_LOG_FILE.read_text(encoding="utf-8"))
        logs_sorted = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)
        return {"total_count": len(logs_sorted), "logs": logs_sorted}
    except Exception:
        raise HTTPException(status_code=500, detail="로그 파일 읽기 실패")


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

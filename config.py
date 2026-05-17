"""API 키 및 전역 설정.

Railway(운영): 환경변수에서 자동 읽기
로컬 개발:    프로젝트 루트의 .env 파일에 키 입력 (python-dotenv 필요)
              또는 셸 환경변수로 직접 설정
"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

VWORLD_API_KEY     = os.environ.get("VWORLD_API_KEY", "")
BUILDING_API_KEY   = os.environ.get("BUILDING_API_KEY", "")
JUSO_API_KEY       = os.environ.get("JUSO_API_KEY", "")
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY", "")
KAKAO_JS_APP_KEY   = os.environ.get("KAKAO_JS_APP_KEY", "")
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")   # 미사용 (Gemini로 교체)
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
LURIS_API_KEY      = os.environ.get("LURIS_API_KEY", "")

API_KEYS = {
    "address":  VWORLD_API_KEY,
    "building": BUILDING_API_KEY,
    "weather":  "",
}

DEFAULTS = {
    "panel_watt":       640,
    "panel_efficiency": 0.20,
    "system_loss":      0.14,
    "panel_width_m":    1.134,
    "panel_height_m":   2.094,
    "min_roof_area_m2": 10,
}

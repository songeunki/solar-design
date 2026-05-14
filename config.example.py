# API 키 설정 예시
# 이 파일을 복사해서 config.py로 저장 후 키를 입력하세요.
# config.py는 .gitignore에 등록되어 있습니다.

VWORLD_API_KEY     = ""  # https://www.vworld.kr 에서 발급
BUILDING_API_KEY   = ""  # https://www.data.go.kr 에서 발급 (건축HUB 건축물대장)
JUSO_API_KEY       = ""  # https://www.juso.go.kr 에서 발급 (도로명→지번 변환)
KAKAO_REST_API_KEY = ""  # https://developers.kakao.com 에서 발급 (정적 지도 보고서 삽입)

API_KEYS = {
    "address":  VWORLD_API_KEY,
    "building": BUILDING_API_KEY,
    "weather":  "",
}

# 태양광 설계 기본값
DEFAULTS = {
    "panel_watt":       400,    # 패널 1장 용량 (W)
    "panel_efficiency": 0.20,   # 패널 효율
    "system_loss":      0.14,   # 시스템 손실률
    "panel_width_m":    1.134,  # 패널 가로 (m)
    "panel_height_m":   2.094,  # 패널 세로 (m)
    "min_roof_area_m2": 10,     # 최소 설치 가능 지붕 면적 (m²)
}

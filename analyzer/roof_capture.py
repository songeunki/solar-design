"""
Playwright로 위성지도 캡처 후 OpenCV로 건물 외곽선 검출.

검출 실패 시 None 반환 → panel_layout.py에서 직사각형 근사로 폴백.
"""
from __future__ import annotations
import base64
import json
import math
import pathlib
import tempfile
import warnings

M_PER_DEG_LAT = 111_320


def detect_building_polygon(
    lat: float,
    lng: float,
    kakao_js_key: str,
) -> list[dict] | None:
    """
    위성지도를 캡처해 건물 외곽선 폴리곤 추출.

    Returns:
        [{lat, lng}] 폴리곤 리스트 또는 None (검출 실패)
    """
    try:
        from playwright.sync_api import sync_playwright
        import cv2
        import numpy as np
    except ImportError as e:
        warnings.warn(f"[RoofCapture] 의존성 없음, 건너뜀: {e}", stacklevel=2)
        return None

    if not kakao_js_key:
        warnings.warn("[RoofCapture] KAKAO_JS_APP_KEY 미설정", stacklevel=2)
        return None

    # ── KakaoMap 위성뷰 HTML ─────────────────────────────────────────────
    w, h = 640, 640
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>html,body,#m{{width:{w}px;height:{h}px;margin:0;padding:0;overflow:hidden}}</style>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_js_key}&autoload=false"></script>
</head><body><div id="m"></div>
<script>
kakao.maps.load(function(){{
  var map=new kakao.maps.Map(document.getElementById('m'),{{
    center:new kakao.maps.LatLng({lat},{lng}),
    level:2,
    mapTypeId:kakao.maps.MapTypeId.SKYVIEW
  }});
  map.setZoomable(false);
  window.__map=map;
  setTimeout(function(){{
    var b=map.getBounds();
    window.__bounds={{
      sw_lat:b.getSouthWest().getLat(),
      sw_lng:b.getSouthWest().getLng(),
      ne_lat:b.getNorthEast().getLat(),
      ne_lng:b.getNorthEast().getLng(),
      w:{w},h:{h}
    }};
    document.title='ready';
  }},2500);
}});
</script></body></html>"""

    tmp = pathlib.Path(tempfile.mktemp(suffix=".html"))
    tmp.write_text(html, encoding="utf-8")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--disable-web-security", "--no-sandbox"])
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto(tmp.as_uri(), wait_until="domcontentloaded")
            try:
                page.wait_for_function("document.title==='ready'", timeout=15000)
            except Exception:
                browser.close()
                return None

            bounds_json = page.evaluate("() => JSON.stringify(window.__bounds)")
            img_bytes   = page.screenshot()
            browser.close()

        bounds = json.loads(bounds_json)
    except Exception as e:
        warnings.warn(f"[RoofCapture] Playwright 실패: {e}", stacklevel=2)
        return None
    finally:
        tmp.unlink(missing_ok=True)

    # ── OpenCV 건물 외곽 검출 ─────────────────────────────────────────────
    try:
        polygon = _detect_contour(img_bytes, bounds, w, h)
    except Exception as e:
        warnings.warn(f"[RoofCapture] OpenCV 처리 실패: {e}", stacklevel=2)
        return None

    return polygon


def _detect_contour(
    img_bytes: bytes,
    bounds: dict,
    w: int,
    h: int,
) -> list[dict] | None:
    """
    이미지에서 중심 건물 윤곽 검출.

    전처리:
        1. 그레이스케일 변환
        2. 가우시안 블러 (노이즈 제거)
        3. Canny 에지 검출
        4. 모폴로지 Closing (에지 연결)
        5. 외부 윤곽 탐색
        6. 면적·위치 필터링
        7. approxPolyDP 단순화
        8. 픽셀 → 위경도 변환
    """
    import cv2
    import numpy as np

    # 이미지 디코딩
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 30, 90)

    # Closing: 끊어진 에지 연결
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    img_area = w * h
    cx, cy = w / 2, h / 2

    # 면적 필터: 이미지의 2%~60%
    candidates = [
        c for c in contours
        if img_area * 0.02 < cv2.contourArea(c) < img_area * 0.60
    ]
    if not candidates:
        return None

    # 중심에 가장 가까운 윤곽 선택
    def dist_to_center(c):
        M = cv2.moments(c)
        if M["m00"] == 0:
            return 1e9
        return math.hypot(M["m10"] / M["m00"] - cx, M["m01"] / M["m00"] - cy)

    best = min(candidates, key=dist_to_center)

    # 폴리곤 단순화 (epsilon = 윤곽 둘레의 2%)
    peri = cv2.arcLength(best, True)
    approx = cv2.approxPolyDP(best, 0.02 * peri, True)

    if len(approx) < 4:
        return None

    # 픽셀 → 위경도 변환
    lat_range = bounds["ne_lat"] - bounds["sw_lat"]
    lng_range = bounds["ne_lng"] - bounds["sw_lng"]

    def px_to_latlng(px: float, py: float) -> dict:
        lat = bounds["ne_lat"] - (py / h) * lat_range
        lng = bounds["sw_lng"] + (px / w) * lng_range
        return {"lat": round(lat, 8), "lng": round(lng, 8)}

    polygon = [px_to_latlng(float(pt[0][0]), float(pt[0][1])) for pt in approx]
    return polygon

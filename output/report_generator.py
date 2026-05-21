import base64
import json
import datetime
import pathlib
import warnings
import requests
from dataclasses import dataclass
from data_collector.building_api import BuildingInfo
from analyzer.roof_analyzer import RoofAnalysis
from designer.electrical import ElectricalDesign
from designer.structural import StructuralDesign

_OUTPUT_DIR = pathlib.Path(__file__).parent / "reports"
_CO2_FACTOR = 0.4599
_REC_WEIGHT = 1.5       # 건물 부착형 소규모 가중치
_REC_PRICE  = 50_000    # 원/REC (현물 시세 추정)

_WIRING_LABELS: dict[str, str] = {
    "dc_cable_mm2":          "DC 케이블 단면적 (mm²)",
    "ac_cable_mm2":          "AC 케이블 단면적 (mm²)",
    "combiner_box_required": "접속함 (Combiner Box)",
    "string_fuse_A":         "스트링 퓨즈 용량 (A)",
    "grounding_scheme":      "접지 방식",
}
_ANCHOR_LABELS: dict[str, str] = {
    "type":               "앙카 종류",
    "embedment_depth_mm": "매입 깊이 (mm)",
    "spacing_m":          "설치 간격 (m)",
    "rail_spacing_m":     "레일 간격 (m)",
    "count_per_panel":    "패널당 앙카 수",
    "total_count":        "총 앙카 수",
    "design_pull_kn":     "설계 인발력 (kN)",
}


try:
    from playwright.sync_api import sync_playwright as _sync_playwright
    _PLAYWRIGHT_OK = True
except Exception:
    _PLAYWRIGHT_OK = False


@dataclass
class Report:
    file_path: str
    pdf_path: str | None
    summary: dict


class ReportGenerator:
    """설계 결과를 HTML + JSON + PDF 보고서로 출력"""

    def generate(
        self,
        address: str,
        building: BuildingInfo,
        roof: RoofAnalysis,
        electrical: ElectricalDesign,
        structural: StructuralDesign,
        lat: float | None = None,
        lng: float | None = None,
        monthly_irradiance: list[float] | None = None,
        solar_altitude_deg: list[float] | None = None,
        panel_layout: dict | None = None,
    ) -> Report:
        _OUTPUT_DIR.mkdir(exist_ok=True)

        ts      = datetime.datetime.now()
        stem    = _file_stem(address, ts)
        summary = _build_summary(
            address, ts, building, roof, electrical, structural,
            monthly_irradiance=monthly_irradiance,
            solar_altitude_deg=solar_altitude_deg,
        )
        map_b64 = _fetch_static_map(lat, lng) if (lat and lng) else None
        html_str = _render_html(summary, map_b64, panel_layout=panel_layout)

        html_path = _OUTPUT_DIR / f"{stem}.html"
        html_path.write_text(html_str, encoding="utf-8")

        json_path = _OUTPUT_DIR / f"{stem}.json"
        json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        pdf_path = _write_pdf(html_str, _OUTPUT_DIR / f"{stem}.pdf")

        return Report(file_path=str(html_path), pdf_path=pdf_path, summary=summary)


def _fetch_static_map(lat: float, lng: float) -> str | None:
    """Playwright로 카카오 지도를 렌더링해 스크린샷 → base64 반환. 실패 시 None."""
    if not _PLAYWRIGHT_OK:
        return None
    try:
        from config import KAKAO_JS_APP_KEY
    except ImportError:
        KAKAO_JS_APP_KEY = ""
    if not KAKAO_JS_APP_KEY:
        try:
            from config import KAKAO_REST_API_KEY as KAKAO_JS_APP_KEY  # fallback
        except ImportError:
            return None

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>html,body,#m{{width:640px;height:280px;margin:0;padding:0;overflow:hidden}}</style>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_APP_KEY}&autoload=false"></script>
</head><body><div id="m"></div><script>
kakao.maps.load(function(){{
    var map=new kakao.maps.Map(document.getElementById('m'),
        {{center:new kakao.maps.LatLng({lat},{lng}),level:3}});
    new kakao.maps.Marker({{position:new kakao.maps.LatLng({lat},{lng}),map:map}});
    setTimeout(function(){{document.title='ready';}},1800);
}});
</script></body></html>"""

    import tempfile
    tmp = pathlib.Path(tempfile.mktemp(suffix=".html"))
    tmp.write_text(html, encoding="utf-8")
    try:
        with _sync_playwright() as pw:
            browser = pw.chromium.launch(
                args=["--disable-web-security", "--no-sandbox"]
            )
            page = browser.new_page(viewport={"width": 640, "height": 280})
            page.goto(tmp.as_uri(), wait_until="domcontentloaded")
            page.wait_for_function("document.title==='ready'", timeout=12000)
            img = page.screenshot()
            browser.close()
        return base64.b64encode(img).decode()
    except Exception as e:
        warnings.warn(f"카카오 지도 스크린샷 실패: {e}", stacklevel=2)
        return None
    finally:
        tmp.unlink(missing_ok=True)


def _fetch_static_map_square(lat: float, lng: float, level: int = 2) -> str | None:
    """3D 뷰어용 정사각형 위성지도 캡처 (512×512). 실패 시 None."""
    if not _PLAYWRIGHT_OK:
        return None
    try:
        from config import KAKAO_JS_APP_KEY
    except ImportError:
        KAKAO_JS_APP_KEY = ""
    if not KAKAO_JS_APP_KEY:
        try:
            from config import KAKAO_REST_API_KEY as KAKAO_JS_APP_KEY
        except ImportError:
            return None

    size = 512
    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>html,body,#m{{width:{size}px;height:{size}px;margin:0;padding:0;overflow:hidden}}</style>
<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_APP_KEY}&autoload=false"></script>
</head><body><div id="m"></div><script>
kakao.maps.load(function(){{
    var map=new kakao.maps.Map(document.getElementById('m'),
        {{center:new kakao.maps.LatLng({lat},{lng}),level:{level},
          mapTypeId:kakao.maps.MapTypeId.SKYVIEW}});
    setTimeout(function(){{document.title='ready';}},2200);
}});
</script></body></html>"""

    import tempfile
    tmp = pathlib.Path(tempfile.mktemp(suffix=".html"))
    tmp.write_text(html, encoding="utf-8")
    try:
        with _sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--disable-web-security", "--no-sandbox"])
            page = browser.new_page(viewport={"width": size, "height": size})
            page.goto(tmp.as_uri(), wait_until="domcontentloaded")
            page.wait_for_function("document.title==='ready'", timeout=14000)
            img = page.screenshot()
            browser.close()
        return base64.b64encode(img).decode()
    except Exception as e:
        warnings.warn(f"정사각형 위성 캡처 실패: {e}", stacklevel=2)
        return None
    finally:
        tmp.unlink(missing_ok=True)


def _write_pdf(html_str: str, dest: pathlib.Path) -> str | None:
    if not _PLAYWRIGHT_OK:
        warnings.warn("playwright를 불러올 수 없어 PDF 생성을 건너뜁니다.", stacklevel=2)
        return None
    import tempfile, shutil
    # set_content()는 대용량 HTML(base64 이미지 포함)에서 PDF가 깨지므로
    # HTML을 임시 파일로 저장 → file:// goto → 별도 ASCII 경로에 PDF 저장 → 최종 경로로 이동
    tmp_html = pathlib.Path(tempfile.mktemp(suffix=".html"))
    tmp_pdf  = pathlib.Path(tempfile.mktemp(suffix=".pdf"))
    tmp_html.write_text(html_str, encoding="utf-8")
    try:
        with _sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(tmp_html.as_uri(), wait_until="networkidle")
            page.pdf(
                path=str(tmp_pdf),
                format="A4",
                margin={"top": "16mm", "bottom": "16mm",
                        "left": "14mm", "right": "14mm"},
                print_background=True,
            )
            browser.close()
        shutil.move(str(tmp_pdf), str(dest))
        return str(dest)
    except Exception as e:
        warnings.warn(f"PDF 생성 실패: {e}", stacklevel=2)
        return None
    finally:
        tmp_html.unlink(missing_ok=True)
        tmp_pdf.unlink(missing_ok=True)


# ── 내부 함수 ─────────────────────────────────────────────────────────────────

def _file_stem(address: str, ts: datetime.datetime) -> str:
    safe = address.replace(" ", "_").replace("/", "-")[:30]
    return f"{safe}_{ts.strftime('%Y%m%d_%H%M%S')}"


def _build_summary(
    address: str,
    ts: datetime.datetime,
    building: BuildingInfo,
    roof: RoofAnalysis,
    electrical: ElectricalDesign,
    structural: StructuralDesign,
    monthly_irradiance: list[float] | None = None,
    solar_altitude_deg: list[float] | None = None,
) -> dict:
    economics = _calc_economics(electrical)
    notes = list(structural.structural_notes)
    if electrical.wiring_spec.get("combiner_box_required"):
        notes.append("직류 접속함(Combiner Box) 설치 필요")

    return {
        "생성일시": ts.isoformat(timespec="seconds"),
        "주소": address,
        "건물정보": {
            "유형": building.building_type,
            "층수": building.floors,
            "지붕면적_m2": building.roof_area_m2,
            "지붕형태": building.roof_type,
            "경사각_deg": building.roof_slope_deg,
            "구조": building.structure,
            "추정값": building.extra.get("fallback", False),
        },
        "지붕분석": {
            "태양고도각": roof.solar_elevations,
            "GCR": roof.gcr,
            "유효면적_m2": roof.usable_area_m2,
            "방위각_deg": roof.azimuth_deg,
            "방위각_보정계수": roof.azimuth_factor,
            "음영손실률": roof.shading_loss,
            "경사각_deg": roof.tilt_deg,
        },
        "태양광시스템": {
            "패널수": electrical.panel_count,
            "총용량_kW": electrical.total_capacity_kw,
            "연간발전량_kWh": electrical.annual_generation_kwh,
            "월별발전량_kWh": electrical.monthly_generation_kwh,
            "월별일사량_kWh_m2": monthly_irradiance or [],
            "월별태양고도각_deg": solar_altitude_deg or [],
            "인버터용량_kW": electrical.inverter_capacity_kw,
            "직병렬구성": electrical.string_config,
            "배선사양": electrical.wiring_spec,
        },
        "구조설계": {
            "마운팅방식": structural.mounting_type,
            "총중량_kg": structural.total_weight_kg,
            "풍하중_kN": structural.wind_load_kn,
            "적설하중_kN": structural.snow_load_kn,
            "앙카사양": structural.anchor_spec,
        },
        "경제성": economics,
        "특이사항": notes,
    }


def _calc_economics(e: ElectricalDesign) -> dict:
    from config import get_admin_finance
    from analyzer.smp_api import get_smp_price
    fin = get_admin_finance()
    cost_per_kw = fin["cost_per_kw"] * 10_000  # 만원 → 원
    smp         = get_smp_price()
    elec_price  = smp["price"]
    smp_date    = smp["date"]
    smp_source  = smp["source"]

    total_cost  = e.total_capacity_kw * cost_per_kw
    annual_save = e.annual_generation_kwh * elec_price
    payback     = total_cost / annual_save if annual_save > 0 else 0.0
    co2         = e.annual_generation_kwh * _CO2_FACTOR
    annual_rec  = round(e.annual_generation_kwh / 1000 * _REC_WEIGHT * _REC_PRICE)
    return {
        "예상설치비_만원":  round(total_cost / 10_000),
        "연간절감액_만원":  round(annual_save / 10_000, 1),
        "연간REC수익_만원": round(annual_rec / 10_000, 1),
        "단순회수기간_년":  round(payback, 1),
        "연간CO2저감_kg":   round(co2),
        "smp_price":        elec_price,
        "smp_date":         smp_date,
        "smp_source":       smp_source,
    }


_MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]


def _monthly_chart(values: list[float], irradiance: list[float] | None = None) -> str:
    """월별 발전량 SVG — 오렌지 막대(발전량) + 파란 꺾은선(일사량, 데이터 있을 때만)"""
    W, H = 680, 220
    PL, PR, PT, PB = 52, 16, 24, 40
    cw = W - PL - PR
    ch = H - PT - PB
    max_v   = max(values)   if values     else 1
    max_irr = max(irradiance) if irradiance else 1
    slot = cw / 12
    bw   = slot * 0.55

    grid, bars, pts = [], [], []
    for pct in [0.25, 0.5, 0.75, 1.0]:
        y = PT + ch * (1 - pct)
        grid += [
            f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>',
            f'<text x="{PL-6}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#a0aec0">{max_v*pct:.0f}</text>',
        ]

    for i, v in enumerate(values):
        bh = (v / max_v) * ch if max_v else 0
        x  = PL + i * slot + (slot - bw) / 2
        y  = PT + ch - bh
        cx = PL + i * slot + slot / 2
        bars += [
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="#FF6B35" opacity="0.9"/>',
            f'<text x="{cx:.1f}" y="{y-5:.1f}" text-anchor="middle" font-size="9" fill="#FF6B35" font-weight="700">{v:.0f}</text>',
            f'<text x="{cx:.1f}" y="{PT+ch+18:.1f}" text-anchor="middle" font-size="10" fill="#718096">{_MONTHS[i]}</text>',
        ]
        if irradiance and i < len(irradiance):
            cy = PT + ch - (irradiance[i] / max_irr) * ch if max_irr else PT + ch
            pts.append(f"{cx:.1f},{cy:.1f}")

    line_svg = ""
    if pts:
        poly = (
            f'<polyline points="{" ".join(pts)}" fill="none" stroke="#1E6FD9"'
            f' stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        dots = "".join(
            f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3.5"'
            f' fill="white" stroke="#1E6FD9" stroke-width="2.5"/>'
            for p in pts
        )
        line_svg = poly + dots

    return (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block">'
        + "".join(grid) + "".join(bars) + line_svg + "</svg>"
    )


def _solar_altitude_chart(altitudes: list[float]) -> str:
    """월별 최대 태양 고도각 SVG — 파란 꺾은선, 계절별 배경 밴드"""
    W, H = 680, 210
    PL, PR, PT, PB = 48, 16, 28, 40
    cw = W - PL - PR
    ch = H - PT - PB
    max_alt = 90.0
    slot = cw / 12

    # 계절 배경 (start_idx, end_idx_exclusive, color)
    season_bands = [
        (0,  2,  "rgba(147,197,253,0.22)"),  # 겨울 (1-2월)
        (2,  5,  "rgba(134,239,172,0.22)"),  # 봄   (3-5월)
        (5,  8,  "rgba(253,186,116,0.22)"),  # 여름 (6-8월)
        (8,  11, "rgba(252,211,77,0.22)"),   # 가을 (9-11월)
        (11, 12, "rgba(147,197,253,0.22)"),  # 겨울 (12월)
    ]
    bands = []
    for s, e, color in season_bands:
        x = PL + s * slot
        w = (e - s) * slot
        bands.append(
            f'<rect x="{x:.1f}" y="{PT}" width="{w:.1f}" height="{ch}"'
            f' fill="{color}" rx="3"/>'
        )

    # Y축 눈금 (0°, 30°, 60°, 90°)
    grid = []
    for v in [0, 30, 60, 90]:
        y = PT + ch - (v / max_alt) * ch
        grid += [
            f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>',
            f'<text x="{PL-6}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#a0aec0">{v}°</text>',
        ]

    # 꺾은선 포인트
    pts, value_labels, x_labels = [], [], []
    for i, alt in enumerate(altitudes):
        cx = PL + i * slot + slot / 2
        cy = PT + ch - (alt / max_alt) * ch
        pts.append(f"{cx:.1f},{cy:.1f}")
        value_labels.append(
            f'<text x="{cx:.1f}" y="{cy-8:.1f}" text-anchor="middle"'
            f' font-size="9" fill="#1E6FD9" font-weight="700">{alt}°</text>'
        )
        x_labels.append(
            f'<text x="{cx:.1f}" y="{PT+ch+18:.1f}" text-anchor="middle"'
            f' font-size="10" fill="#718096">{_MONTHS[i]}</text>'
        )

    poly = (
        f'<polyline points="{" ".join(pts)}" fill="none" stroke="#1E6FD9"'
        f' stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>'
    )
    dots = "".join(
        f'<circle cx="{p.split(",")[0]}" cy="{p.split(",")[1]}" r="3.5"'
        f' fill="white" stroke="#1E6FD9" stroke-width="2.5"/>'
        for p in pts
    )
    x_axis = f'<line x1="{PL}" y1="{PT+ch}" x2="{W-PR}" y2="{PT+ch}" stroke="#e2e8f0" stroke-width="1.5"/>'

    return (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block">'
        + "".join(bands) + "".join(grid)
        + poly + dots + "".join(value_labels) + "".join(x_labels) + x_axis
        + "</svg>"
    )


def _panel_layout_svg(layout: dict) -> str:
    """패널 배치도 SVG 생성."""
    panels       = layout.get("panels", [])
    roof_poly    = layout.get("roof_polygon", [])
    pw_deg       = layout.get("panel_w_deg_lng", 0)
    ph_deg       = layout.get("panel_h_deg_lat", 0)
    stats        = layout.get("stats", {})

    if not panels:
        return ""

    W, H = 680, 420
    PAD  = {"t": 28, "r": 28, "b": 48, "l": 28}
    dw   = W - PAD["l"] - PAD["r"]
    dh   = H - PAD["t"] - PAD["b"]

    all_lats = [p["lat"] for p in panels] + [p["lat"] + ph_deg for p in panels]
    all_lngs = [p["lng"] for p in panels] + [p["lng"] + pw_deg for p in panels]
    if roof_poly:
        all_lats += [p["lat"] for p in roof_poly]
        all_lngs += [p["lng"] for p in roof_poly]

    min_lat, max_lat = min(all_lats), max(all_lats)
    min_lng, max_lng = min(all_lngs), max(all_lngs)
    lat_r = max_lat - min_lat or 1e-9
    lng_r = max_lng - min_lng or 1e-9

    def tx(lng):  return PAD["l"] + (lng  - min_lng) / lng_r * dw
    def ty(lat):  return PAD["t"] + (max_lat - lat)  / lat_r * dh

    # 지붕 윤곽
    roof_pts = " ".join(f"{tx(p['lng']):.1f},{ty(p['lat']):.1f}" for p in roof_poly)
    roof_svg = (
        f'<polygon points="{roof_pts}" fill="rgba(241,245,249,0.9)"'
        f' stroke="#a0aec0" stroke-width="1.5" stroke-dasharray="6,3"/>'
        if roof_pts else ""
    )

    # 패널
    px_w = max(2, pw_deg / lng_r * dw)
    px_h = max(2, ph_deg / lat_r * dh)

    color_map = {
        "active": ("#1E6FD9", "rgba(30,111,217,0.65)"),
        "shade":  ("#b91c1c", "rgba(220,38,38,0.50)"),
        "buffer": ("#718096", "rgba(160,174,192,0.35)"),
    }
    panel_svgs = []
    for p in panels:
        sc, fc = color_map.get(p["status"], color_map["active"])
        x = tx(p["lng"])
        y = ty(p["lat"] + ph_deg)
        panel_svgs.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{px_w:.1f}" height="{px_h:.1f}"'
            f' rx="1" fill="{fc}" stroke="{sc}" stroke-width="0.5"/>'
        )

    # 범례
    legend = (
        f'<rect x="{PAD["l"]}" y="{H-34}" width="12" height="8" rx="1" fill="rgba(30,111,217,0.65)" stroke="#1E6FD9" stroke-width="0.5"/>'
        f'<text x="{PAD["l"]+16}" y="{H-27}" font-size="10" fill="#4a5568">설치 패널 ({stats.get("active_panels","-")}매)</text>'
        f'<rect x="{PAD["l"]+130}" y="{H-34}" width="12" height="8" rx="1" fill="rgba(220,38,38,0.50)" stroke="#b91c1c" stroke-width="0.5"/>'
        f'<text x="{PAD["l"]+146}" y="{H-27}" font-size="10" fill="#4a5568">음영 구역 ({stats.get("shaded_panels","-")}매)</text>'
        f'<text x="{W-PAD["r"]}" y="{H-27}" text-anchor="end" font-size="10" fill="#718096">'
        f'이격 {stats.get("row_spacing_m","?")}m | {stats.get("row_count","?")}행×{stats.get("col_count","?")}열</text>'
    )

    # 나침반
    compass = (
        f'<circle cx="{W-PAD["r"]-14}" cy="{PAD["t"]+14}" r="14" fill="white" stroke="#e2e8f0" stroke-width="1"/>'
        f'<polygon points="{W-PAD["r"]-14},{PAD["t"]}" fill="#1E6FD9"/>'  # N
        f'<text x="{W-PAD["r"]-14}" y="{PAD["t"]-2}" text-anchor="middle" font-size="8" font-weight="700" fill="#1E6FD9">N</text>'
    )

    return (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block;'
        f'background:#f8faff;border-radius:8px;border:1px solid #e2e8f0">'
        + roof_svg + "".join(panel_svgs) + legend + compass
        + "</svg>"
    )


def _fmt(v) -> str:
    """값 포맷: bool → 한국어, 나머지 → 문자열"""
    if isinstance(v, bool):
        return "필요" if v else "불필요"
    return str(v)


def _rows(d: dict, labels: dict | None = None) -> str:
    return "".join(
        f"<tr><th>{labels.get(k, k) if labels else k}</th><td>{_fmt(v)}</td></tr>"
        for k, v in d.items()
    )


def _azimuth_label(deg: float) -> str:
    labels = ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    return labels[round(deg / 45) % 8]


def _elev_bar(deg: float, max_deg: float = 90.0) -> str:
    """태양 고도각을 인라인 바 차트로 표현"""
    pct = deg / max_deg * 100
    color = "#1565c0" if deg < 35 else ("#f59e0b" if deg < 60 else "#16a34a")
    return (
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<div style="flex:1;background:#eef1f8;border-radius:4px;height:9px">'
        f'<div style="width:{pct:.1f}%;height:100%;background:{color};border-radius:4px"></div>'
        f'</div>'
        f'<span style="font-weight:700;min-width:42px;color:{color}">{deg}°</span>'
        f'</div>'
    )


def _render_html(s: dict, map_b64: str | None = None, panel_layout: dict | None = None) -> str:  # noqa: C901
    b  = s["건물정보"]
    r  = s["지붕분석"]
    e  = s["태양광시스템"]
    st = s["구조설계"]
    ec = s["경제성"]
    date_str = s["생성일시"].replace("T", " ")

    # ── 인라인 헬퍼 (f-string 내부 중괄호 문제 방지를 위해 함수로 분리) ──────

    def row(label: str, value: str, color: str = "#1a202c") -> str:
        return (
            '<div style="display:flex;justify-content:space-between;align-items:center;'
            'padding:10px 0;border-bottom:1px solid #f0f3f9;font-size:14px">'
            f'<span style="color:#4a5568">{label}</span>'
            f'<span style="font-weight:600;color:{color}">{value}</span>'
            '</div>'
        )

    def sub_label(text: str) -> str:
        return (
            '<div style="font-size:11px;font-weight:700;color:#1E6FD9;'
            'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px">'
            f'{text}</div>'
        )

    def two_col(left: str, right: str) -> str:
        return (
            '<div class="two-col-grid" style="display:grid;'
            'grid-template-columns:1fr 1fr;gap:32px">'
            f'<div>{left}</div><div>{right}</div></div>'
        )

    def card(title: str, body: str) -> str:
        return (
            '<div style="background:#fff;border-radius:12px;padding:28px 32px;'
            'box-shadow:0 4px 16px rgba(0,0,0,0.08);border:1px solid #e2e8f0;'
            'border-top:3px solid #1E6FD9;margin-bottom:20px">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:20px;'
            'padding-bottom:14px;border-bottom:1.5px solid #eef1f8">'
            '<div style="width:4px;height:18px;background:#1E6FD9;border-radius:2px"></div>'
            f'<span style="font-size:15px;font-weight:700;color:#1a202c">{title}</span>'
            '</div>'
            + body + '</div>'
        )

    # ── 지도 ─────────────────────────────────────────────────────────────────
    map_html = ""
    if map_b64:
        map_html = (
            '<div style="max-width:1080px;margin:0 auto;padding:0 24px 24px">'
            '<div style="border-radius:12px;overflow:hidden;'
            'box-shadow:0 4px 16px rgba(0,0,0,0.08)">'
            f'<img src="data:image/png;base64,{map_b64}"'
            ' style="width:100%;display:block" alt="위치"/>'
            f'<div style="background:#fff;padding:10px 18px;font-size:13px;'
            f'color:#718096">📍 {s["주소"]}</div>'
            '</div></div>'
        )

    # ── KPI 카드 ──────────────────────────────────────────────────────────────
    kpi_items = [
        ("⚡", f"{e['총용량_kW']}", "kWp", "설치 용량",       "#1E6FD9", "#e8f0fc"),
        ("☀️", f"{e['연간발전량_kWh']:,.0f}", "kWh", "연간 발전량", "#FF6B35", "#fff1ec"),
        ("💰", f"{ec['연간절감액_만원']:,.1f}", "만원", "연간 절감액",  "#2ecc71", "#e8f8f0"),
        ("📈", f"{ec['단순회수기간_년']}", "년",  "투자 회수 기간", "#1E6FD9", "#e8f0fc"),
        ("🌿", f"{ec['연간CO2저감_kg']:,}", "kg",  "CO₂ 저감량",  "#2ecc71", "#e8f8f0"),
    ]
    kpi_html = "".join(
        '<div style="background:#fff;border-radius:12px;padding:20px;'
        'box-shadow:0 4px 16px rgba(0,0,0,0.08);border:1px solid #e2e8f0;'
        f'border-bottom:3px solid {c};display:flex;align-items:center;gap:14px">'
        '<div style="flex:1">'
        f'<div style="font-size:11px;font-weight:600;color:#a0aec0;'
        f'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px">{lbl}</div>'
        f'<div style="font-size:24px;font-weight:800;color:#1a202c;line-height:1">{val}'
        f'<span style="font-size:13px;font-weight:500;color:#4a5568;margin-left:3px">{u}</span></div>'
        '</div>'
        f'<div style="width:46px;height:46px;border-radius:12px;background:{ibg};'
        f'display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0">{ic}</div>'
        '</div>'
        for ic, val, u, lbl, c, ibg in kpi_items
    )

    # ── 건물 정보 ─────────────────────────────────────────────────────────────
    building_section = card("🏢 건물 정보",
        row("건물 유형", b["유형"]) +
        row("지상 층수", f"{b['층수']}층") +
        row("건축면적 (지붕 기준)", f"{b['지붕면적_m2']:,.1f} m²") +
        row("지붕 형태", b["지붕형태"]) +
        row("지붕 경사각", f"{b['경사각_deg']}°") +
        row("건물 구조", b["구조"])
    )

    # ── 지붕 분석 ─────────────────────────────────────────────────────────────
    roof_left = (
        sub_label("절기별 정오 태양 고도각 (서울 37.5°N)") +
        row("동지 (12/21)",  f"{r['태양고도각']['동지']}°") +
        row("춘추분 (3/21)", f"{r['태양고도각']['춘추분']}°") +
        row("하지 (6/21)",   f"{r['태양고도각']['하지']}°")
    )
    roof_right = (
        sub_label("배치 설계 파라미터") +
        row("GCR", str(r["GCR"])) +
        row("유효 설치 면적", f"{r['유효면적_m2']:,.1f} m²") +
        row("방위각", f"{r['방위각_deg']:.0f}° ({_azimuth_label(r['방위각_deg'])}향)") +
        row("방위각 보정계수", f"{r['방위각_보정계수']:.3f}") +
        row("음영 손실률", f"{r['음영손실률']*100:.1f}%") +
        row("패널 설치 경사각", f"{r['경사각_deg']:.0f}°")
    )
    roof_section = card("🔍 지붕 분석", two_col(roof_left, roof_right))

    # ── 태양광 시스템 ─────────────────────────────────────────────────────────
    ws = e["배선사양"]
    sys_left = (
        sub_label("시스템 기본 사양") +
        row("패널 수", f"{e['패널수']}장") +
        row("시스템 총 용량", f"{e['총용량_kW']} kWp") +
        row("연간 예상 발전량", f"{e['연간발전량_kWh']:,.0f} kWh", "#1E6FD9") +
        row("인버터 용량", f"{e['인버터용량_kW']} kW") +
        row("직병렬 구성", e["직병렬구성"])
    )
    sys_right = (
        sub_label("배선 사양 (KEC 기준)") +
        row("DC 케이블 단면적", f"{ws.get('dc_cable_mm2', '-')} mm²") +
        row("AC 케이블 단면적", f"{ws.get('ac_cable_mm2', '-')} mm²") +
        row("접속함 (Combiner Box)", "필요" if ws.get("combiner_box_required") else "불필요") +
        row("스트링 퓨즈 용량", f"{ws.get('string_fuse_A', '-')} A") +
        row("접지 방식", ws.get("grounding_scheme", "-"))
    )
    system_section = card("⚡ 태양광 시스템 사양", two_col(sys_left, sys_right))

    # ── 월별 발전량 ───────────────────────────────────────────────────────────
    irr_data = e.get("월별일사량_kWh_m2") or None
    chart_legend_items = (
        '<div style="display:flex;align-items:center;gap:6px;font-size:12px;'
        'font-weight:500;color:#4a5568">'
        '<div style="width:10px;height:10px;border-radius:2px;background:#FF6B35"></div>'
        '월별 발전량 (kWh)</div>'
    )
    if irr_data:
        chart_legend_items += (
            '<div style="display:flex;align-items:center;gap:6px;font-size:12px;'
            'font-weight:500;color:#4a5568">'
            '<div style="width:10px;height:10px;border-radius:50%;background:#1E6FD9"></div>'
            '일사량 (kWh/m²)</div>'
        )
    chart_legend = (
        '<div style="display:flex;gap:20px;margin-bottom:12px;flex-wrap:wrap">'
        + chart_legend_items + '</div>'
    )
    chart_note = (
        '<div style="font-size:11px;color:#a0aec0;text-align:right;margin-top:4px">'
        '단위: kWh / 월</div>'
    )
    chart_section = card(
        "📊 월별 예상 발전량",
        chart_legend + _monthly_chart(e["월별발전량_kWh"], irradiance=irr_data) + chart_note
    )

    # ── 월별 태양 고도각 ──────────────────────────────────────────────────────
    alt_data = e.get("월별태양고도각_deg") or []
    alt_legend = (
        '<div style="display:flex;gap:20px;margin-bottom:12px;flex-wrap:wrap;align-items:center">'
        '<div style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500;color:#4a5568">'
        '<div style="width:10px;height:10px;border-radius:50%;background:#1E6FD9"></div>'
        '월별 최대 태양 고도각 (°)</div>'
        '<div style="display:flex;gap:14px;margin-left:auto">'
        + "".join(
            '<div style="display:flex;align-items:center;gap:4px;font-size:11px;color:#4a5568">'
            f'<div style="width:8px;height:8px;border-radius:2px;background:{c}"></div>{lbl}</div>'
            for lbl, c in [
                ("봄",   "rgba(134,239,172,0.8)"),
                ("여름", "rgba(253,186,116,0.8)"),
                ("가을", "rgba(252,211,77,0.8)"),
                ("겨울", "rgba(147,197,253,0.8)"),
            ]
        )
        + '</div></div>'
    )
    alt_note = (
        '<div style="font-size:11px;color:#a0aec0;text-align:right;margin-top:4px">'
        '단위: ° (도) · 서울 위도 기준 최대 고도각</div>'
    )
    altitude_section = (
        card("☀️ 월별 태양 고도각", alt_legend + _solar_altitude_chart(alt_data) + alt_note)
        if alt_data else ""
    )

    # ── 구조 설계 ─────────────────────────────────────────────────────────────
    anc = st["앙카사양"]
    str_left = (
        sub_label("하중 및 마운팅") +
        row("마운팅 방식", st["마운팅방식"]) +
        row("패널 + 마운트 총 중량", f"{st['총중량_kg']:,.1f} kg") +
        row("설계 풍하중 (KBC 2022)", f"{st['풍하중_kN']} kN") +
        row("설계 적설하중 (KBC 2022)", f"{st['적설하중_kN']} kN")
    )
    str_right = (
        sub_label("앙카 사양") +
        row("앙카 종류", anc.get("type", "-")) +
        row("패널당 앙카 수", str(anc.get("count_per_panel", "-"))) +
        row("총 앙카 수", str(anc.get("total_count", "-"))) +
        row("설계 인발력", f"{anc.get('design_pull_kn', '-')} kN")
    )
    structural_section = card("🔩 구조 설계", two_col(str_left, str_right))

    # ── 패널 배치도 ───────────────────────────────────────────────────────────
    if panel_layout and panel_layout.get("panels"):
        pl_stats = panel_layout.get("stats", {})
        pl_legend = (
            '<div style="display:flex;gap:20px;margin-bottom:12px;flex-wrap:wrap;align-items:center">'
            '<div style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500;color:#4a5568">'
            '<div style="width:12px;height:8px;border-radius:2px;background:rgba(30,111,217,0.65);border:1px solid #1E6FD9"></div>'
            f'설치 패널 ({pl_stats.get("active_panels", "-")}매)</div>'
            '<div style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:500;color:#4a5568">'
            '<div style="width:12px;height:8px;border-radius:2px;background:rgba(220,38,38,0.50);border:1px solid #b91c1c"></div>'
            f'음영 구역 ({pl_stats.get("shaded_panels", "-")}매)</div>'
            f'<div style="margin-left:auto;font-size:11px;color:#718096">'
            f'{pl_stats.get("row_count","?")}행 × {pl_stats.get("col_count","?")}열 · '
            f'행 이격 {pl_stats.get("row_spacing_m","?")}m</div>'
            '</div>'
        )
        pl_note = (
            '<div style="font-size:11px;color:#a0aec0;margin-top:8px">'
            f'동지 태양 고도각 기준 최소 이격 {pl_stats.get("min_gap_m","?")}m 적용 — 음영 없는 최적 배치</div>'
        )
        panel_layout_section = card(
            "🔲 태양광 패널 가상 배치도",
            pl_legend + _panel_layout_svg(panel_layout) + pl_note
        )
    else:
        panel_layout_section = ""

    # ── 경제성 분석 ───────────────────────────────────────────────────────────
    ec_left = (
        row("예상 설치비", f"약 {ec['예상설치비_만원']:,} 만원") +
        row("연간 전기 절감액", f"약 {ec['연간절감액_만원']:,} 만원 / 년", "#FF6B35")
    )
    ec_right = (
        row("단순 투자 회수 기간", f"{ec['단순회수기간_년']} 년", "#1E6FD9") +
        row("연간 CO₂ 저감량", f"{ec['연간CO2저감_kg']:,} kg-CO₂ / 년", "#2ecc71")
    )
    _smp_price  = ec.get("smp_price", 150)
    _smp_source = ec.get("smp_source", "관리자 설정 기준")
    _smp_date   = ec.get("smp_date")
    _smp_label  = f"{_smp_source} {_smp_date}" if _smp_date else _smp_source
    ec_note = (
        '<div style="margin-top:16px;padding:12px 16px;background:#f8faff;'
        'border-radius:8px;font-size:12px;color:#718096;border:1px solid #e2e8f0">'
        f'💡 설치비 150만원/kW · 전기단가 {_smp_price:.0f}원/kWh ({_smp_label}) · CO₂ 배출계수 0.4599 kg/kWh '
        '(2023년 기준) 추정값입니다.</div>'
    )
    economics_section = card("💰 경제성 분석", two_col(ec_left, ec_right) + ec_note)

    # ── 특이사항 ──────────────────────────────────────────────────────────────
    notes_items = s["특이사항"]
    notes_body = (
        "".join(
            '<div style="background:#fffbeb;border-left:3px solid #f59e0b;'
            'padding:10px 14px;border-radius:0 8px 8px 0;font-size:13px;'
            f'color:#78450a;margin-bottom:8px">⚠️ {n}</div>'
            for n in notes_items
        ) or '<p style="color:#a0aec0;font-size:14px">특이사항 없음</p>'
    )
    notes_section = card("⚠️ 특이사항 및 권고사항", notes_body)

    # ── 최종 HTML 조립 ───────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>태양광 설계 보고서 — {s['주소']}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;900&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
      background: #F5F7FA;
      color: #1a202c;
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }}

    @media (max-width: 768px) {{
      .kpi-grid {{ grid-template-columns: repeat(2,1fr) !important; gap:10px !important; }}
      .two-col-grid {{ grid-template-columns: 1fr !important; gap:16px !important; }}
      .main-pad {{ padding: 16px 14px 40px !important; }}
      h1 {{ font-size: 1.4rem !important; }}
    }}
    @media print {{
      body {{ background:#fff; }}
      div[style*="box-shadow"] {{ box-shadow:none !important; border:1px solid #e2e8f0; page-break-inside:avoid; }}
    }}
  </style>
</head>
<body>

<!-- 헤더 -->
<div style="background:linear-gradient(135deg,#0a2744 0%,#1E6FD9 55%,#42a5f5 100%);color:#fff;padding:40px 48px 36px">
  <div style="display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);border-radius:20px;padding:4px 14px;font-size:12px;letter-spacing:0.07em;margin-bottom:14px">
    ☀ AI 태양광 입지 분석 자동화 프로그램
  </div>
  <h1 style="font-size:28px;font-weight:900;letter-spacing:-0.3px;margin-bottom:12px">태양광 설계 분석 보고서</h1>
  <div style="display:flex;flex-wrap:wrap;gap:6px 28px;font-size:14px;opacity:0.88">
    <span>📍 {s['주소']}</span>
    <span>🗓 {date_str}</span>
  </div>
</div>

{map_html}

<div class="main-pad" style="max-width:1080px;margin:0 auto;padding:28px 24px 56px">

  <!-- KPI -->
  <div class="kpi-grid" style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:24px">
    {kpi_html}
  </div>

  {building_section}
  {roof_section}
  {system_section}
  {chart_section}
  {altitude_section}
  {panel_layout_section}
  {structural_section}
  {economics_section}
  {notes_section}

</div>

<div style="text-align:center;padding:20px;font-size:12px;color:#a0aec0">
  AI 태양광 입지 분석 자동화 프로그램 &nbsp;·&nbsp; {date_str} 생성
</div>

</body>
</html>"""




# ══════════════════════════════════════════════════════════════════════════════
# 비교 보고서
# ══════════════════════════════════════════════════════════════════════════════

# (섹션명, [(표시명, 추출함수, 포맷함수, higher_is_better)])
# higher_is_better: True=높을수록 녹색, False=낮을수록 녹색, None=강조 없음
_COMPARE_SECTIONS: list[tuple] = [
    ("건물 기본 정보", [
        ("건물 유형",      lambda s: s["건물정보"]["유형"],              str,                            None),
        ("지상 층수",      lambda s: s["건물정보"]["층수"],              lambda v: f"{v}층",              None),
        ("건축면적",       lambda s: s["건물정보"]["지붕면적_m2"],       lambda v: f"{v:,.1f} m²",        None),
        ("지붕 형태",      lambda s: s["건물정보"]["지붕형태"],          str,                            None),
        ("구조",           lambda s: s["건물정보"]["구조"],              str,                            None),
    ]),
    ("지붕 분석", [
        ("유효 설치 면적", lambda s: s["지붕분석"]["유효면적_m2"],       lambda v: f"{v:,.1f} m²",        True),
        ("GCR",            lambda s: s["지붕분석"]["GCR"],              lambda v: f"{v:.3f}",            True),
        ("방위각",         lambda s: s["지붕분석"]["방위각_deg"],        lambda v: f"{v:.0f}°",           None),
        ("방위각 보정계수", lambda s: s["지붕분석"]["방위각_보정계수"],   lambda v: f"{v:.3f}",            True),
        ("음영 손실률",    lambda s: s["지붕분석"]["음영손실률"],        lambda v: f"{v*100:.1f}%",       False),
        ("패널 경사각",    lambda s: s["지붕분석"]["경사각_deg"],        lambda v: f"{v:.0f}°",           None),
        ("동지 고도각",    lambda s: s["지붕분석"]["태양고도각"]["동지"], lambda v: f"{v}°",               None),
    ]),
    ("태양광 시스템", [
        ("패널 수",        lambda s: s["태양광시스템"]["패널수"],        lambda v: f"{v:,}장",            True),
        ("시스템 용량",    lambda s: s["태양광시스템"]["총용량_kW"],     lambda v: f"{v} kWp",            True),
        ("연간 발전량",    lambda s: s["태양광시스템"]["연간발전량_kWh"], lambda v: f"{v:,} kWh",         True),
        ("인버터 용량",    lambda s: s["태양광시스템"]["인버터용량_kW"], lambda v: f"{v} kW",             None),
        ("직병렬 구성",    lambda s: s["태양광시스템"]["직병렬구성"],    str,                            None),
    ]),
    ("경제성", [
        ("예상 설치비",    lambda s: s["경제성"]["예상설치비_만원"],     lambda v: f"{v:,} 만원",         None),
        ("연간 절감액",    lambda s: s["경제성"]["연간절감액_만원"],     lambda v: f"{v:,.1f} 만원",      True),
        ("투자 회수 기간", lambda s: s["경제성"]["단순회수기간_년"],     lambda v: f"{v} 년",             False),
        ("연간 CO₂ 저감",  lambda s: s["경제성"]["연간CO2저감_kg"],     lambda v: f"{v:,} kg",           True),
    ]),
]


@dataclass
class ComparisonReport:
    file_path: str
    pdf_path: str | None
    addresses: list[str]


class ComparisonReportGenerator:
    """여러 주소 설계 결과를 나란히 비교하는 HTML 보고서 생성"""

    def generate(self, results: list[dict]) -> ComparisonReport:
        _OUTPUT_DIR.mkdir(exist_ok=True)
        ts = datetime.datetime.now()

        summaries = [
            _build_summary(
                r["address"], ts,
                r["building"], r["roof"],
                r["electrical"], r["structural"],
            )
            for r in results
        ]

        html_str  = _render_comparison_html(summaries, ts)
        stem      = f"comparison_{ts.strftime('%Y%m%d_%H%M%S')}"
        html_path = _OUTPUT_DIR / f"{stem}.html"
        html_path.write_text(html_str, encoding="utf-8")

        pdf_path = _write_pdf(html_str, _OUTPUT_DIR / f"{stem}.pdf")

        return ComparisonReport(
            file_path=str(html_path),
            pdf_path=pdf_path,
            addresses=[s["주소"] for s in summaries],
        )


def _short_addr(addr: str) -> str:
    """주소 마지막 2개 토큰만 반환 (컬럼 헤더용)"""
    parts = addr.split()
    return " ".join(parts[-2:]) if len(parts) >= 2 else addr


def _render_comparison_html(summaries: list[dict], ts: datetime.datetime) -> str:
    n        = len(summaries)
    date_str = ts.strftime("%Y-%m-%d %H:%M:%S")
    addresses = [s["주소"] for s in summaries]

    # ── 컬럼 헤더 ──────────────────────────────────────────────────────────
    col_headers = "".join(
        f'<th class="col-head">'
        f'<div class="col-num">건물 {i+1}</div>'
        f'<div class="col-addr" title="{addr}">{_short_addr(addr)}</div>'
        f'</th>'
        for i, addr in enumerate(addresses)
    )

    # ── 비교 테이블 행 ─────────────────────────────────────────────────────
    table_body = ""
    for section_name, metrics in _COMPARE_SECTIONS:
        table_body += (
            f'<tr class="section-row">'
            f'<td colspan="{n + 1}">{section_name}</td>'
            f'</tr>'
        )
        for label, extractor, formatter, higher_is_better in metrics:
            raw  = [extractor(s) for s in summaries]
            disp = [formatter(v) for v in raw]

            # 강조: 수치 비교 가능한 경우에만
            cls = [""] * n
            if higher_is_better is not None and all(isinstance(v, (int, float)) for v in raw):
                best  = max(raw) if higher_is_better else min(raw)
                worst = min(raw) if higher_is_better else max(raw)
                for j, v in enumerate(raw):
                    if n > 1 and v == best:
                        cls[j] = " best"
                    elif n > 1 and v == worst:
                        cls[j] = " worst"

            cells = "".join(
                f'<td class="val{cls[j]}">{disp[j]}</td>'
                for j in range(n)
            )
            table_body += f'<tr><th class="metric">{label}</th>{cells}</tr>'

    # ── KPI 카드 (건물별 요약) ─────────────────────────────────────────────
    def kpi_cards(s: dict, idx: int) -> str:
        e  = s["태양광시스템"]
        ec = s["경제성"]
        return f"""
        <div class="bld-card">
          <div class="bld-card-title">건물 {idx+1}</div>
          <div class="bld-card-addr">{s['주소']}</div>
          <div class="bld-kpis">
            <div class="bld-kpi"><div class="bk-val">{e['패널수']}</div><div class="bk-lbl">패널 (장)</div></div>
            <div class="bld-kpi"><div class="bk-val">{e['총용량_kW']}</div><div class="bk-lbl">용량 (kWp)</div></div>
            <div class="bld-kpi"><div class="bk-val">{e['연간발전량_kWh']:,}</div><div class="bk-lbl">연간발전 (kWh)</div></div>
            <div class="bld-kpi"><div class="bk-val">{ec['단순회수기간_년']}</div><div class="bk-lbl">회수기간 (년)</div></div>
          </div>
        </div>"""

    cards_html = "".join(kpi_cards(s, i) for i, s in enumerate(summaries))

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>태양광 설계 비교 보고서</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
      background: #eef1f7; color: #1a2332; line-height: 1.6;
    }}

    .header {{
      background: linear-gradient(135deg, #0a2744 0%, #1565c0 55%, #42a5f5 100%);
      color: #fff; padding: 40px 52px 36px;
    }}
    .header-badge {{
      display: inline-flex; align-items: center; gap: 6px;
      background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.3);
      border-radius: 20px; padding: 4px 14px; font-size: 0.76em;
      letter-spacing: 0.07em; margin-bottom: 14px;
    }}
    .header h1 {{ font-size: 1.8em; font-weight: 800; margin-bottom: 8px; }}
    .header-meta {{ font-size: 0.86em; opacity: 0.85; }}

    .container {{ max-width: 1100px; margin: 0 auto; padding: 28px 20px 56px; }}

    /* 건물 카드 */
    .bld-grid {{
      display: grid;
      grid-template-columns: repeat({n}, 1fr);
      gap: 14px; margin-bottom: 24px;
    }}
    .bld-card {{
      background: #fff; border-radius: 14px;
      padding: 20px 18px; box-shadow: 0 2px 12px rgba(0,0,0,0.07);
      border-top: 3px solid #1565c0;
    }}
    .bld-card-title {{ font-size: 0.78em; font-weight: 700; color: #1565c0;
      text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 4px; }}
    .bld-card-addr {{ font-size: 0.88em; color: #334155; margin-bottom: 16px;
      line-height: 1.4; }}
    .bld-kpis {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .bld-kpi {{ background: #f8faff; border-radius: 8px; padding: 10px 8px; text-align: center; }}
    .bk-val {{ font-size: 1.25em; font-weight: 800; color: #0a2744; }}
    .bk-lbl {{ font-size: 0.7em; color: #7888a4; margin-top: 3px; }}

    /* 비교 테이블 */
    .section {{
      background: #fff; border-radius: 14px; padding: 0;
      box-shadow: 0 2px 12px rgba(0,0,0,0.06); overflow: hidden;
    }}
    .section-title {{
      font-size: 1.02em; font-weight: 700; color: #0a2744;
      display: flex; align-items: center; gap: 10px;
      padding: 22px 28px 18px; border-bottom: 1.5px solid #eef1f8;
    }}

    .compare-wrap {{ overflow-x: auto; }}
    table.compare {{ width: 100%; border-collapse: collapse; }}

    table.compare thead th {{
      background: #0a2744; color: #fff;
      padding: 0; text-align: center;
      font-size: 0.82em; position: sticky; top: 0; z-index: 2;
    }}
    table.compare thead th:first-child {{
      background: #0d3060; text-align: left;
      padding: 14px 20px; min-width: 140px;
      position: sticky; left: 0; z-index: 3;
    }}
    .col-head {{ padding: 12px 16px; }}
    .col-num {{ font-size: 0.72em; opacity: 0.7; margin-bottom: 3px; }}
    .col-addr {{ font-weight: 700; }}

    table.compare tbody tr {{ border-bottom: 1px solid #f0f3f9; }}
    table.compare tbody tr:last-child {{ border-bottom: none; }}

    /* 섹션 구분 행 */
    tr.section-row td {{
      background: #e8f0fe; color: #1565c0;
      font-size: 0.78em; font-weight: 700;
      text-transform: uppercase; letter-spacing: 0.07em;
      padding: 8px 20px;
    }}

    /* 항목명 열 */
    th.metric {{
      text-align: left; padding: 10px 20px;
      font-size: 0.83em; color: #7888a4; font-weight: 600;
      background: #fff; position: sticky; left: 0;
      border-right: 1px solid #f0f3f9; min-width: 140px;
    }}

    /* 값 셀 */
    td.val {{
      text-align: center; padding: 10px 16px;
      font-size: 0.92em; font-weight: 500; color: #1a2332;
      transition: background 0.15s;
    }}
    td.val.best {{
      background: #dcfce7; color: #15803d; font-weight: 700;
    }}
    td.val.worst {{
      background: #fef2f2; color: #dc2626;
    }}

    .legend {{
      display: flex; gap: 20px; align-items: center;
      font-size: 0.78em; color: #7888a4;
      padding: 14px 20px; border-top: 1px solid #f0f3f9;
    }}
    .legend-item {{ display: flex; align-items: center; gap: 6px; }}
    .legend-dot {{
      width: 12px; height: 12px; border-radius: 3px;
    }}

    .footer {{
      text-align: center; padding: 20px;
      font-size: 0.78em; color: #a0aec0;
    }}

    /* ── Mobile ── */
    @media (max-width: 768px) {{
      body {{ font-size: 0.88rem; }}
      .header {{ padding: 24px 16px 20px; }}
      .header h1 {{ font-size: 1.35rem; }}
      .container {{ padding: 16px 12px 40px; }}
      .bld-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-badge">☀ 태양광 설계 자동화 시스템</div>
  <h1>설계 비교 보고서</h1>
  <div class="header-meta">건물 {n}개 비교 &nbsp;·&nbsp; {date_str} 생성</div>
</div>

<div class="container">

  <!-- 건물 요약 카드 -->
  <div class="bld-grid">
    {cards_html}
  </div>

  <!-- 비교 테이블 -->
  <div class="section">
    <div class="section-title">상세 비교</div>
    <div class="compare-wrap">
      <table class="compare">
        <thead>
          <tr>
            <th>항목</th>
            {col_headers}
          </tr>
        </thead>
        <tbody>
          {table_body}
        </tbody>
      </table>
    </div>
    <div class="legend">
      <div class="legend-item">
        <div class="legend-dot" style="background:#dcfce7;border:1px solid #16a34a"></div>
        <span>해당 항목 최우수 값</span>
      </div>
      <div class="legend-item">
        <div class="legend-dot" style="background:#fef2f2;border:1px solid #dc2626"></div>
        <span>해당 항목 최하위 값</span>
      </div>
    </div>
  </div>

</div>

<div class="footer">
  태양광 설계 자동화 시스템 &nbsp;·&nbsp; {date_str} 생성
</div>

</body>
</html>"""

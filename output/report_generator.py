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

_OUTPUT_DIR  = pathlib.Path(__file__).parent / "reports"
_COST_PER_KW = 1_500_000
_ELEC_PRICE  = 120
_CO2_FACTOR  = 0.4599

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
    ) -> Report:
        _OUTPUT_DIR.mkdir(exist_ok=True)

        ts      = datetime.datetime.now()
        stem    = _file_stem(address, ts)
        summary = _build_summary(address, ts, building, roof, electrical, structural)
        map_b64 = _fetch_static_map(lat, lng) if (lat and lng) else None
        html_str = _render_html(summary, map_b64)

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
    total_cost  = e.total_capacity_kw * _COST_PER_KW
    annual_save = e.annual_generation_kwh * _ELEC_PRICE
    payback     = total_cost / annual_save if annual_save > 0 else 0.0
    co2         = e.annual_generation_kwh * _CO2_FACTOR
    return {
        "예상설치비_만원":  round(total_cost / 10_000),
        "연간절감액_만원":  round(annual_save / 10_000, 1),
        "단순회수기간_년":  round(payback, 1),
        "연간CO2저감_kg":   round(co2),
    }


_MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]


def _monthly_chart(values: list[float]) -> str:
    """월별 발전량 SVG 막대 차트 생성"""
    W, H = 660, 210
    pl, pr, pt, pb = 46, 12, 24, 38   # padding: left, right, top, bottom
    cw = W - pl - pr                   # chart width  602
    ch = H - pt - pb                   # chart height 148

    max_v = max(values) if values else 1
    bar_slot = cw / 12
    bw = bar_slot * 0.68               # bar width
    gap = (bar_slot - bw) / 2

    # Y축 눈금선 4개
    grid_lines = []
    for pct in [0.25, 0.5, 0.75, 1.0]:
        y = pt + ch * (1 - pct)
        label = f"{max_v * pct:.0f}"
        grid_lines.append(
            f'<line x1="{pl}" y1="{y:.1f}" x2="{W-pr}" y2="{y:.1f}" '
            f'stroke="#eef1f8" stroke-width="1.2"/>'
        )
        grid_lines.append(
            f'<text x="{pl-5}" y="{y+3.5:.1f}" text-anchor="end" '
            f'font-size="9.5" fill="#a0aec0">{label}</text>'
        )

    # 막대 + 라벨
    bars = []
    for i, v in enumerate(values):
        bh = (v / max_v) * ch if max_v else 0
        x  = pl + i * bar_slot + gap
        y  = pt + ch - bh
        cx = pl + i * bar_slot + bar_slot / 2   # 막대 중앙 x

        # 하이라이트: 최대·최솟값 색상 구분
        if v == max(values):
            fill = "url(#barHigh)"
        elif v == min(values):
            fill = "url(#barLow)"
        else:
            fill = "url(#barNorm)"

        bars.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
            f'rx="3" fill="{fill}"/>'
        )
        # 값 레이블 (막대 위)
        bars.append(
            f'<text x="{cx:.1f}" y="{y-5:.1f}" text-anchor="middle" '
            f'font-size="9" fill="#4a6fa5" font-weight="600">{v:.0f}</text>'
        )
        # 월 레이블 (아래)
        bars.append(
            f'<text x="{cx:.1f}" y="{pt+ch+20:.1f}" text-anchor="middle" '
            f'font-size="10" fill="#8898b4">{_MONTHS[i]}</text>'
        )

    return f"""<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block">
  <defs>
    <linearGradient id="barNorm" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1565c0"/>
      <stop offset="100%" stop-color="#5ea5f0"/>
    </linearGradient>
    <linearGradient id="barHigh" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#f59e0b"/>
      <stop offset="100%" stop-color="#fbbf24"/>
    </linearGradient>
    <linearGradient id="barLow" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#64b5f6"/>
      <stop offset="100%" stop-color="#90caf9"/>
    </linearGradient>
  </defs>
  {"".join(grid_lines)}
  {"".join(bars)}
</svg>"""


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


def _render_html(s: dict, map_b64: str | None = None) -> str:
    b  = s["건물정보"]
    r  = s["지붕분석"]
    e  = s["태양광시스템"]
    st = s["구조설계"]
    ec = s["경제성"]
    date_str   = s["생성일시"].replace("T", " ")
    notes_html = "".join(
        f'<div class="alert">{n}</div>' for n in s["특이사항"]
    ) or '<p class="no-note">특이사항 없음</p>'
    chart_svg  = _monthly_chart(e["월별발전량_kWh"])
    map_section = (
        f'<div style="max-width:980px;margin:0 auto;padding:20px 24px 0">'
        f'<div style="border-radius:14px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.1)">'
        f'<img src="data:image/png;base64,{map_b64}" style="width:100%;height:auto;display:block" alt="건물 위치 지도"/>'
        f'<div style="background:#fff;padding:10px 18px;font-size:0.82em;color:#7888a4">📍 {s["주소"]}</div>'
        f'</div></div>'
    ) if map_b64 else ''

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>태양광 설계 보고서 — {s['주소']}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
      background: #eef1f7;
      color: #1a2332;
      line-height: 1.65;
    }}

    /* ── Header ── */
    .header {{
      background: linear-gradient(135deg, #0a2744 0%, #1565c0 55%, #42a5f5 100%);
      color: #fff;
      padding: 44px 52px 40px;
    }}
    .header-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(255,255,255,0.15);
      border: 1px solid rgba(255,255,255,0.3);
      border-radius: 20px;
      padding: 4px 14px;
      font-size: 0.76em;
      letter-spacing: 0.07em;
      margin-bottom: 16px;
    }}
    .header h1 {{
      font-size: 1.9em;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 14px;
    }}
    .header-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px 28px;
      font-size: 0.88em;
      opacity: 0.88;
    }}

    /* ── Container ── */
    .container {{ max-width: 980px; margin: 0 auto; padding: 32px 24px 56px; }}

    /* ── KPI Grid ── */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 14px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: #fff;
      border-radius: 14px;
      padding: 22px 14px 18px;
      text-align: center;
      box-shadow: 0 2px 12px rgba(0,0,0,0.07);
      border-top: 3px solid #1565c0;
    }}
    .kpi-icon {{ font-size: 1.55em; margin-bottom: 7px; }}
    .kpi-val  {{ font-size: 1.85em; font-weight: 800; color: #0a2744; line-height: 1.15; }}
    .kpi-lbl  {{ font-size: 0.74em; color: #7888a4; margin-top: 5px; }}

    /* ── Section card ── */
    .section {{
      background: #fff;
      border-radius: 14px;
      padding: 28px 32px;
      margin-bottom: 20px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }}
    .section-title {{
      font-size: 1.02em;
      font-weight: 700;
      color: #0a2744;
      display: flex;
      align-items: center;
      gap: 10px;
      padding-bottom: 14px;
      margin-bottom: 20px;
      border-bottom: 1.5px solid #eef1f8;
    }}
    .section-num {{
      background: #1565c0;
      color: #fff;
      border-radius: 50%;
      width: 26px; height: 26px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 0.8em;
      font-weight: 700;
      flex-shrink: 0;
    }}

    /* ── Two-column layout ── */
    .two-col {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 36px;
    }}
    .sub-label {{
      font-size: 0.72em;
      font-weight: 700;
      color: #1565c0;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 10px;
    }}

    /* ── Table ── */
    table {{ width: 100%; border-collapse: collapse; }}
    tr {{ border-bottom: 1px solid #f0f3f9; }}
    tr:last-child {{ border-bottom: none; }}
    th {{
      width: 48%;
      padding: 9px 0;
      color: #8898b4;
      font-weight: 600;
      font-size: 0.83em;
      text-align: left;
      vertical-align: top;
    }}
    td {{
      padding: 9px 0 9px 6px;
      color: #1a2332;
      font-size: 0.92em;
      font-weight: 500;
    }}

    /* ── Alert ── */
    .alert {{
      background: #fffbeb;
      border-left: 3px solid #f59e0b;
      padding: 10px 14px;
      border-radius: 0 8px 8px 0;
      font-size: 0.89em;
      color: #78450a;
      margin-bottom: 8px;
    }}
    .alert::before {{ content: "[주의] "; }}
    .no-note {{ font-size: 0.9em; color: #a0aec0; }}

    /* ── Footnote ── */
    .footnote {{
      font-size: 0.78em;
      color: #a0aec0;
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid #eef1f8;
    }}

    /* ── Footer ── */
    .footer {{
      text-align: center;
      padding: 20px;
      font-size: 0.78em;
      color: #a0aec0;
    }}

    /* ── Mobile ── */
    .table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}

    @media (max-width: 768px) {{
      body {{ font-size: 0.9rem; }}
      .header {{ padding: 24px 16px 20px; }}
      .header h1 {{ font-size: 1.4rem; }}
      .header-meta {{ font-size: 0.82rem; gap: 4px 14px; }}
      .container {{ padding: 16px 12px 40px; }}
      .kpi-grid {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
      .kpi-val {{ font-size: 1.4rem; }}
      .kpi-lbl {{ font-size: 0.72rem; }}
      .section {{ padding: 20px 16px; }}
      .two-col {{ grid-template-columns: 1fr; gap: 20px; }}
      th {{ font-size: 0.78rem; }}
      td {{ font-size: 0.86rem; }}
    }}

    @media print {{
      body {{ background: #fff; }}
      .section, .kpi-card {{ box-shadow: none; border: 1px solid #e2e8f0; page-break-inside: avoid; }}
    }}
  </style>
</head>
<body>

<div class="header">
  <div class="header-badge">☀ 태양광 설계 자동화 시스템</div>
  <h1>설계 보고서</h1>
  <div class="header-meta">
    <span>📍 {s['주소']}</span>
    <span>🗓 {date_str}</span>
  </div>
</div>

{map_section}

<div class="container">

  <!-- KPI 카드 -->
  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-icon">🔆</div>
      <div class="kpi-val">{e['패널수']}</div>
      <div class="kpi-lbl">패널 수 (장)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">⚡</div>
      <div class="kpi-val">{e['총용량_kW']}</div>
      <div class="kpi-lbl">시스템 용량 (kWp)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">📊</div>
      <div class="kpi-val">{e['연간발전량_kWh']:,.0f}</div>
      <div class="kpi-lbl">연간 발전량 (kWh)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">💰</div>
      <div class="kpi-val">{ec['단순회수기간_년']}</div>
      <div class="kpi-lbl">투자 회수 기간 (년)</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-icon">🌿</div>
      <div class="kpi-val">{ec['연간CO2저감_kg']:,}</div>
      <div class="kpi-lbl">CO₂ 저감 (kg/년)</div>
    </div>
  </div>

  <!-- 1. 건물 정보 -->
  <div class="section">
    <div class="section-title"><span class="section-num">1</span> 건물 정보</div>
    <table>
      <tr><th>건물 유형</th><td>{b['유형']}</td></tr>
      <tr><th>지상 층수</th><td>{b['층수']} 층</td></tr>
      <tr><th>건축면적 (지붕 기준)</th><td>{b['지붕면적_m2']:,.1f} m²</td></tr>
      <tr><th>지붕 형태</th><td>{b['지붕형태']}</td></tr>
      <tr><th>지붕 경사각</th><td>{b['경사각_deg']} °</td></tr>
      <tr><th>건물 구조</th><td>{b['구조']}</td></tr>
    </table>
  </div>

  <!-- 2. 지붕 분석 -->
  <div class="section">
    <div class="section-title"><span class="section-num">2</span> 지붕 분석</div>
    <div class="two-col">
      <div>
        <div class="sub-label">절기별 정오 태양 고도각 (서울 37.5°N)</div>
        <table>
          <tr>
            <th>동지 (12/21)</th>
            <td>{_elev_bar(r['태양고도각']['동지'])}</td>
          </tr>
          <tr>
            <th>춘추분 (3/21)</th>
            <td>{_elev_bar(r['태양고도각']['춘추분'])}</td>
          </tr>
          <tr>
            <th>하지 (6/21)</th>
            <td>{_elev_bar(r['태양고도각']['하지'])}</td>
          </tr>
        </table>
        <div style="font-size:0.76em;color:#a0aec0;margin-top:10px">
          동지 기준(최저 고도각)으로 행간 이격거리 및 GCR 산정 — 보수적 설계
        </div>
      </div>
      <div>
        <div class="sub-label">배치 설계 파라미터</div>
        <table>
          <tr>
            <th>GCR (Ground Coverage Ratio)</th>
            <td><strong>{r['GCR']}</strong>
              <span style="font-size:0.82em;color:#7888a4;margin-left:4px">
                (동지 무음영 기준)
              </span>
            </td>
          </tr>
          <tr><th>유효 설치 면적</th><td>{r['유효면적_m2']:,.1f} m²</td></tr>
          <tr>
            <th>방위각</th>
            <td>{r['방위각_deg']:.0f}° ({_azimuth_label(r['방위각_deg'])}향)</td>
          </tr>
          <tr>
            <th>방위각 보정계수</th>
            <td>
              <strong style="color:{'#16a34a' if r['방위각_보정계수'] >= 0.99 else '#dc2626'}">
                {r['방위각_보정계수']:.3f}
              </strong>
              <span style="font-size:0.82em;color:#7888a4;margin-left:4px">
                (남향 대비 {r['방위각_보정계수']*100:.1f}%)
              </span>
            </td>
          </tr>
          <tr>
            <th>음영 손실률</th>
            <td>{r['음영손실률']*100:.1f}%</td>
          </tr>
          <tr><th>패널 설치 경사각</th><td>{r['경사각_deg']:.0f}°</td></tr>
        </table>
      </div>
    </div>
  </div>

  <!-- 3. 태양광 시스템 -->
  <div class="section">
    <div class="section-title"><span class="section-num">3</span> 태양광 시스템 사양</div>
    <div class="two-col">
      <div>
        <div class="sub-label">시스템 기본 사양</div>
        <table>
          <tr><th>패널 수</th><td>{e['패널수']} 장</td></tr>
          <tr><th>시스템 총 용량</th><td>{e['총용량_kW']} kWp</td></tr>
          <tr><th>연간 예상 발전량</th><td>{e['연간발전량_kWh']:,.0f} kWh</td></tr>
          <tr><th>인버터 용량</th><td>{e['인버터용량_kW']} kW</td></tr>
          <tr><th>직병렬 구성</th><td>{e['직병렬구성']}</td></tr>
        </table>
      </div>
      <div>
        <div class="sub-label">배선 사양 (KEC 기준)</div>
        <table>{_rows(e['배선사양'], _WIRING_LABELS)}</table>
      </div>
    </div>
  </div>

  <!-- 4. 월별 발전량 차트 -->
  <div class="section">
    <div class="section-title"><span class="section-num">4</span> 월별 예상 발전량
      <span style="margin-left:auto;font-size:0.8em;font-weight:400;color:#a0aec0">
        ■ 최대 &nbsp; ■ 평균 &nbsp; ■ 최소
      </span>
    </div>
    <div style="margin-bottom:6px">
      {chart_svg}
    </div>
    <div style="font-size:0.78em;color:#a0aec0;text-align:right">단위: kWh / 월</div>
  </div>

  <!-- 5. 구조 설계 -->
  <div class="section">
    <div class="section-title"><span class="section-num">5</span> 구조 설계</div>
    <div class="two-col">
      <div>
        <div class="sub-label">하중 및 마운팅</div>
        <table>
          <tr><th>마운팅 방식</th><td>{st['마운팅방식']}</td></tr>
          <tr><th>패널 + 마운트 총 중량</th><td>{st['총중량_kg']:,.1f} kg</td></tr>
          <tr><th>설계 풍하중 (KBC 2022)</th><td>{st['풍하중_kN']} kN</td></tr>
          <tr><th>설계 적설하중 (KBC 2022)</th><td>{st['적설하중_kN']} kN</td></tr>
        </table>
      </div>
      <div>
        <div class="sub-label">앙카 사양</div>
        <table>{_rows(st['앙카사양'], _ANCHOR_LABELS)}</table>
      </div>
    </div>
  </div>

  <!-- 6. 경제성 분석 -->
  <div class="section">
    <div class="section-title"><span class="section-num">6</span> 경제성 분석</div>
    <table>
      <tr><th>예상 설치비</th><td>약 {ec['예상설치비_만원']:,} 만원</td></tr>
      <tr><th>연간 전기 절감액</th><td>약 {ec['연간절감액_만원']:,} 만원 / 년</td></tr>
      <tr><th>단순 투자 회수 기간</th><td>{ec['단순회수기간_년']} 년</td></tr>
      <tr><th>연간 CO₂ 저감량</th><td>{ec['연간CO2저감_kg']:,} kg-CO₂ / 년</td></tr>
    </table>
    <div class="footnote">
      설치비 150만원/kW · 전기단가 120원/kWh · CO₂ 배출계수 0.4599 kg/kWh (2023년 기준) 추정값입니다.
    </div>
  </div>

  <!-- 7. 특이사항 -->
  <div class="section">
    <div class="section-title"><span class="section-num">7</span> 특이사항</div>
    {notes_html}
  </div>

</div>

<div class="footer">
  태양광 설계 자동화 시스템 &nbsp;·&nbsp; {date_str} 생성
</div>

<script>
document.querySelectorAll('.section table, .two-col table').forEach(function(t){{
  var w = document.createElement('div');
  w.className = 'table-wrap';
  t.parentNode.insertBefore(w, t);
  w.appendChild(t);
}});
</script>

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

import json, pathlib, datetime

a = json.loads(pathlib.Path("reports/서울특별시_강남구_삼성동_169_20260512_124947.json").read_text("utf-8"))
b = json.loads(pathlib.Path("reports/부산광역시_강서구_체육공원로6번길_109_20260512_125812.json").read_text("utf-8"))

MONTHS = ["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"]


def bar_chart(vals_a, vals_b):
    max_v = max(max(vals_a), max(vals_b))
    W, H = 700, 230
    pl, pr, pt, pb = 48, 12, 28, 40
    cw = W - pl - pr
    ch = H - pt - pb
    slot = cw / 12
    bw = slot * 0.36
    gap = slot * 0.06

    def make_bar(i, v, offset, color, label_color):
        bh = (v / max_v) * ch if max_v else 0
        x  = pl + i * slot + gap + offset
        y  = pt + ch - bh
        cx = x + bw / 2
        return [
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{color}"/>',
            f'<text x="{cx:.1f}" y="{y-4:.1f}" text-anchor="middle" font-size="8" fill="{label_color}">{v:.0f}</text>',
        ]

    grids = []
    for pct in [0.25, 0.5, 0.75, 1.0]:
        y = pt + ch * (1 - pct)
        grids += [
            f'<line x1="{pl}" y1="{y:.1f}" x2="{W-pr}" y2="{y:.1f}" stroke="#eef1f8" stroke-width="1"/>',
            f'<text x="{pl-4}" y="{y+3:.1f}" text-anchor="end" font-size="9" fill="#a0aec0">{max_v*pct:.0f}</text>',
        ]

    bars = []
    for i, (va, vb) in enumerate(zip(vals_a, vals_b)):
        bars += make_bar(i, va, 0,          "#1565c0", "#1565c0")
        bars += make_bar(i, vb, bw + gap,   "#e65100", "#b45309")
        cx = pl + i * slot + slot / 2
        bars.append(f'<text x="{cx:.1f}" y="{pt+ch+22:.1f}" text-anchor="middle" font-size="10" fill="#8898b4">{MONTHS[i]}</text>')

    return (
        f'<svg viewBox="0 0 {W} {H}" style="width:100%;height:{H}px;display:block">'
        + "".join(grids) + "".join(bars)
        + "</svg>"
    )


def diff_badge(va, vb, fmt=".0f", unit=""):
    d = vb - va
    sign = "+" if d >= 0 else ""
    color = "#16a34a" if d >= 0 else "#dc2626"
    return f'<span style="color:{color};font-size:0.82em;font-weight:700">{sign}{d:{fmt}}{unit}</span>'


ea = a["태양광시스템"]; eb = b["태양광시스템"]
eca = a["경제성"];      ecb = b["경제성"]
ba  = a["건물정보"];    bb  = b["건물정보"]
sta = a["구조설계"];    stb = b["구조설계"]

chart_svg = bar_chart(ea["월별발전량_kWh"], eb["월별발전량_kWh"])
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

notes_a = "".join(f'<div class="alert">{n}</div>' for n in a["특이사항"]) or '<p class="no-note">없음</p>'
notes_b = "".join(f'<div class="alert alert-b">{n}</div>' for n in b["특이사항"]) or '<p class="no-note">없음</p>'

html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>태양광 설계 비교 보고서</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;background:#eef1f7;color:#1a2332;line-height:1.65}}
    .header{{background:linear-gradient(135deg,#0a2744 0%,#1565c0 55%,#42a5f5 100%);color:#fff;padding:36px 52px 32px}}
    .header-badge{{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);border-radius:20px;padding:4px 14px;font-size:.76em;letter-spacing:.07em;margin-bottom:14px}}
    .header h1{{font-size:1.75em;font-weight:800;letter-spacing:-.02em;margin-bottom:8px}}
    .header-meta{{font-size:.86em;opacity:.85}}
    .container{{max-width:1100px;margin:0 auto;padding:28px 20px 52px}}
    .addr-grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:20px}}
    .addr-card{{border-radius:12px;padding:16px 20px;color:#fff;font-weight:700;font-size:1em}}
    .addr-a{{background:linear-gradient(135deg,#1565c0,#42a5f5)}}
    .addr-b{{background:linear-gradient(135deg,#b45309,#f97316)}}
    .addr-card .label{{font-size:.75em;opacity:.85;margin-bottom:4px;font-weight:400}}
    .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}}
    .kpi-card{{background:#fff;border-radius:14px;padding:20px 16px;box-shadow:0 2px 12px rgba(0,0,0,.06)}}
    .kpi-title{{font-size:.74em;color:#7888a4;margin-bottom:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}}
    .kpi-row{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:3px}}
    .kpi-val-a{{font-size:1.5em;font-weight:800;color:#1565c0}}
    .kpi-val-b{{font-size:1.5em;font-weight:800;color:#e65100}}
    .kpi-lbl{{font-size:.78em;color:#a0aec0}}
    .kpi-diff{{text-align:right;margin-top:8px;padding-top:8px;border-top:1px solid #f0f3f9;font-size:.8em;color:#6b7a99}}
    .section{{background:#fff;border-radius:14px;padding:26px 30px;margin-bottom:18px;box-shadow:0 2px 10px rgba(0,0,0,.06)}}
    .section-title{{font-size:1em;font-weight:700;color:#0a2744;display:flex;align-items:center;gap:10px;padding-bottom:14px;margin-bottom:18px;border-bottom:1.5px solid #eef1f8}}
    .section-num{{background:#1565c0;color:#fff;border-radius:50%;width:24px;height:24px;display:inline-flex;align-items:center;justify-content:center;font-size:.78em;font-weight:700;flex-shrink:0}}
    .cmp-table{{width:100%;border-collapse:collapse}}
    .cmp-table tr{{border-bottom:1px solid #f0f3f9}}
    .cmp-table tr:last-child{{border-bottom:none}}
    .cmp-table th{{padding:10px 0;color:#8898b4;font-weight:600;font-size:.83em;text-align:left;width:28%}}
    .cmp-table td{{padding:10px 6px;font-size:.92em;font-weight:500;width:36%}}
    .cmp-table td.a{{color:#1565c0}}
    .cmp-table td.b{{color:#e65100}}
    .cmp-table tr:hover{{background:#fafbff}}
    .legend{{display:flex;gap:20px;font-size:.83em;color:#6b7a99;margin-bottom:12px}}
    .dot{{width:12px;height:12px;border-radius:2px;display:inline-block;margin-right:5px;vertical-align:middle}}
    .dot-a{{background:#1565c0}}
    .dot-b{{background:#e65100}}
    .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
    .sub-label{{font-size:.72em;font-weight:700;color:#1565c0;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px}}
    .sub-label-b{{color:#e65100}}
    .alert{{background:#fffbeb;border-left:3px solid #f59e0b;padding:9px 14px;border-radius:0 8px 8px 0;font-size:.87em;color:#78450a;margin-bottom:7px}}
    .alert::before{{content:"⚠ "}}
    .alert-b{{border-left-color:#e65100;color:#7c2d12}}
    .no-note{{font-size:.88em;color:#a0aec0}}
    .footer{{text-align:center;padding:18px;font-size:.78em;color:#a0aec0}}
    @media print{{body{{background:#fff}}.section,.kpi-card{{box-shadow:none;border:1px solid #e2e8f0;page-break-inside:avoid}}}}
  </style>
</head>
<body>

<div class="header">
  <div class="header-badge">☀ 태양광 설계 자동화 시스템 — 비교 보고서</div>
  <h1>설계 비교 보고서</h1>
  <div class="header-meta">🗓 {now} 생성</div>
</div>

<div class="container">

  <div class="addr-grid">
    <div class="addr-card addr-a"><div class="label">A 주소</div>{a['주소']}</div>
    <div class="addr-card addr-b"><div class="label">B 주소</div>{b['주소']}</div>
  </div>

  <div class="kpi-grid">
    <div class="kpi-card">
      <div class="kpi-title">시스템 용량 (kWp)</div>
      <div class="kpi-row"><span class="kpi-val-a">{ea['총용량_kW']}</span><span class="kpi-lbl">A</span></div>
      <div class="kpi-row"><span class="kpi-val-b">{eb['총용량_kW']}</span><span class="kpi-lbl">B</span></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">연간 발전량 (kWh)</div>
      <div class="kpi-row"><span class="kpi-val-a">{ea['연간발전량_kWh']:,}</span><span class="kpi-lbl">A</span></div>
      <div class="kpi-row"><span class="kpi-val-b">{eb['연간발전량_kWh']:,}</span><span class="kpi-lbl">B</span></div>
      <div class="kpi-diff">B − A {diff_badge(ea['연간발전량_kWh'], eb['연간발전량_kWh'], '.0f', ' kWh')}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">투자 회수 기간 (년)</div>
      <div class="kpi-row"><span class="kpi-val-a">{eca['단순회수기간_년']}</span><span class="kpi-lbl">A</span></div>
      <div class="kpi-row"><span class="kpi-val-b">{ecb['단순회수기간_년']}</span><span class="kpi-lbl">B</span></div>
      <div class="kpi-diff">B − A {diff_badge(eca['단순회수기간_년'], ecb['단순회수기간_년'], '.1f', '년')}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-title">연간 CO₂ 저감 (kg)</div>
      <div class="kpi-row"><span class="kpi-val-a">{eca['연간CO2저감_kg']:,}</span><span class="kpi-lbl">A</span></div>
      <div class="kpi-row"><span class="kpi-val-b">{ecb['연간CO2저감_kg']:,}</span><span class="kpi-lbl">B</span></div>
      <div class="kpi-diff">B − A {diff_badge(eca['연간CO2저감_kg'], ecb['연간CO2저감_kg'], '.0f', ' kg')}</div>
    </div>
  </div>

  <div class="section">
    <div class="section-title"><span class="section-num">1</span> 건물 정보</div>
    <table class="cmp-table">
      <tr><th></th><td class="a"><b>A</b> 서울 강남</td><td class="b"><b>B</b> 부산 강서</td></tr>
      <tr><th>건물 유형</th><td class="a">{ba['유형']}</td><td class="b">{bb['유형']}</td></tr>
      <tr><th>지상 층수</th><td class="a">{ba['층수']} 층</td><td class="b">{bb['층수']} 층</td></tr>
      <tr><th>건축면적</th><td class="a">{ba['지붕면적_m2']:,.1f} m²</td><td class="b">{bb['지붕면적_m2']:,.1f} m²</td></tr>
      <tr><th>지붕 형태</th><td class="a">{ba['지붕형태']}</td><td class="b">{bb['지붕형태']}</td></tr>
      <tr><th>구조</th><td class="a">{ba['구조']}</td><td class="b">{bb['구조']}</td></tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title"><span class="section-num">2</span> 태양광 시스템 사양</div>
    <table class="cmp-table">
      <tr><th></th><td class="a"><b>A</b> 서울 강남</td><td class="b"><b>B</b> 부산 강서</td></tr>
      <tr><th>패널 수</th><td class="a">{ea['패널수']} 장</td><td class="b">{eb['패널수']} 장</td></tr>
      <tr><th>총 용량</th><td class="a">{ea['총용량_kW']} kWp</td><td class="b">{eb['총용량_kW']} kWp</td></tr>
      <tr><th>연간 발전량</th><td class="a">{ea['연간발전량_kWh']:,} kWh</td><td class="b">{eb['연간발전량_kWh']:,} kWh</td></tr>
      <tr><th>인버터 용량</th><td class="a">{ea['인버터용량_kW']} kW</td><td class="b">{eb['인버터용량_kW']} kW</td></tr>
      <tr><th>직병렬 구성</th><td class="a">{ea['직병렬구성']}</td><td class="b">{eb['직병렬구성']}</td></tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title"><span class="section-num">3</span> 월별 발전량 비교</div>
    <div class="legend">
      <span><span class="dot dot-a"></span>A — {a['주소'][:12]}</span>
      <span><span class="dot dot-b"></span>B — {b['주소'][:12]}</span>
    </div>
    {chart_svg}
    <div style="font-size:.78em;color:#a0aec0;text-align:right;margin-top:6px">단위: kWh / 월</div>
  </div>

  <div class="section">
    <div class="section-title"><span class="section-num">4</span> 경제성 분석</div>
    <table class="cmp-table">
      <tr><th></th><td class="a"><b>A</b> 서울 강남</td><td class="b"><b>B</b> 부산 강서</td></tr>
      <tr><th>예상 설치비</th><td class="a">약 {eca['예상설치비_만원']:,} 만원</td><td class="b">약 {ecb['예상설치비_만원']:,} 만원</td></tr>
      <tr><th>연간 절감액</th><td class="a">약 {eca['연간절감액_만원']:,} 만원/년</td><td class="b">약 {ecb['연간절감액_만원']:,} 만원/년</td></tr>
      <tr><th>투자 회수 기간</th><td class="a">{eca['단순회수기간_년']} 년</td><td class="b">{ecb['단순회수기간_년']} 년</td></tr>
      <tr><th>연간 CO₂ 저감</th><td class="a">{eca['연간CO2저감_kg']:,} kg</td><td class="b">{ecb['연간CO2저감_kg']:,} kg</td></tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title"><span class="section-num">5</span> 구조 설계</div>
    <table class="cmp-table">
      <tr><th></th><td class="a"><b>A</b> 서울 강남</td><td class="b"><b>B</b> 부산 강서</td></tr>
      <tr><th>마운팅 방식</th>
        <td class="a">{sta['마운팅방식'].split('—')[0].strip()}</td>
        <td class="b">{stb['마운팅방식'].split('—')[0].strip()}</td>
      </tr>
      <tr><th>총 중량</th><td class="a">{sta['총중량_kg']:,.1f} kg</td><td class="b">{stb['총중량_kg']:,.1f} kg</td></tr>
      <tr><th>설계 풍하중</th><td class="a">{sta['풍하중_kN']} kN</td><td class="b">{stb['풍하중_kN']} kN</td></tr>
      <tr><th>설계 적설하중</th><td class="a">{sta['적설하중_kN']} kN</td><td class="b">{stb['적설하중_kN']} kN</td></tr>
    </table>
  </div>

  <div class="section">
    <div class="section-title"><span class="section-num">6</span> 특이사항</div>
    <div class="two-col">
      <div>
        <div class="sub-label">A — 서울 강남</div>
        {notes_a}
      </div>
      <div>
        <div class="sub-label sub-label-b">B — 부산 강서</div>
        {notes_b}
      </div>
    </div>
  </div>

</div>
<div class="footer">태양광 설계 자동화 시스템 &nbsp;·&nbsp; {now} 생성</div>
</body>
</html>"""

out = pathlib.Path("reports/comparison_강남_부산.html")
out.write_text(html, encoding="utf-8")
print(f"저장: {out.resolve()}  ({out.stat().st_size // 1024} KB)")

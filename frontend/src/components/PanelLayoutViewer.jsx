/**
 * PanelLayoutViewer — SVG 패널 배치도 + 월별 음영 시뮬레이션
 * props:
 *   layout  - panel_layout 객체
 *   lat     - 건물 위도 (음영 계산용)
 */
import { useState, useMemo } from 'react';
import { calcShadeMatrix, shadeToColor, MONTH_LABELS, SIM_MONTHS } from '../utils/solar.js';

const BASE_COLOR = {
  active: { fill: 'rgba(30,111,217,0.65)', stroke: '#1565c0' },
  shade:  { fill: 'rgba(220,38,38,0.50)',  stroke: '#b91c1c' },
};

const TAB_MONTHS = SIM_MONTHS; // [0, 3, 6, 9] → 1월, 4월, 7월, 10월

export default function PanelLayoutViewer({ layout, lat = 37.5 }) {
  const [tooltip,    setTooltip]    = useState(null);
  const [shadeMonth, setShadeMonth] = useState(null); // null = 기본 배치도

  if (!layout?.panels?.length) return null;

  const { panels, roof_polygon, panel_w_deg_lng: pw, panel_h_deg_lat: ph, stats } = layout;

  // ── 음영 행렬 계산 (선택 월) ───────────────────────────────────────────
  const shadeMatrix = useMemo(() => {
    if (shadeMonth === null) return null;
    return calcShadeMatrix(panels, stats, lat, shadeMonth);
  }, [panels, stats, lat, shadeMonth]);

  // ── SVG 좌표계 ────────────────────────────────────────────────────────
  const SVG_W = 620, SVG_H = 420;
  const PAD   = { top: 28, right: 28, bottom: 52, left: 28 };
  const drawW = SVG_W - PAD.left - PAD.right;
  const drawH = SVG_H - PAD.top  - PAD.bottom;

  const allLats = [...(roof_polygon ?? []).map(p => p.lat), ...panels.flatMap(p => [p.lat, p.lat + ph])];
  const allLngs = [...(roof_polygon ?? []).map(p => p.lng), ...panels.flatMap(p => [p.lng, p.lng + pw])];
  const minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
  const minLng = Math.min(...allLngs), maxLng = Math.max(...allLngs);
  const latR = maxLat - minLat || 1e-9;
  const lngR = maxLng - minLng || 1e-9;

  const toX = (lng) => PAD.left  + ((lng  - minLng) / lngR) * drawW;
  const toY = (lat) => PAD.top   + ((maxLat - lat)  / latR) * drawH;

  const roofPts = (roof_polygon ?? []).map(p => `${toX(p.lng)},${toY(p.lat)}`).join(' ');
  const pxW = Math.max(2, (pw / lngR) * drawW);
  const pxH = Math.max(2, (ph / latR) * drawH);

  // ── 그라데이션 범례 (음영 모드) ────────────────────────────────────────
  const GradientDef = () => (
    <defs>
      <linearGradient id="shadGrad" x1="0" x2="1" y1="0" y2="0">
        <stop offset="0%"   stopColor={shadeToColor(0)} />
        <stop offset="50%"  stopColor={shadeToColor(0.5)} />
        <stop offset="100%" stopColor={shadeToColor(1)} />
      </linearGradient>
    </defs>
  );

  return (
    <div className="chart-wrapper">
      {/* ── 탭 바 ── */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          onClick={() => setShadeMonth(null)}
          style={{
            padding: '6px 14px', borderRadius: 8, border: 'none', cursor: 'pointer',
            fontWeight: 600, fontSize: 13, transition: 'all 0.15s',
            background: shadeMonth === null ? 'var(--blue)' : 'var(--bg)',
            color:      shadeMonth === null ? 'white' : 'var(--text-secondary)',
          }}
        >
          🔲 기본 배치도
        </button>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', margin: '0 4px' }}>|</span>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>음영 시뮬레이션:</span>
        {TAB_MONTHS.map((m) => (
          <button
            key={m}
            onClick={() => setShadeMonth(m)}
            style={{
              padding: '6px 12px', borderRadius: 8, border: 'none', cursor: 'pointer',
              fontWeight: 600, fontSize: 12, transition: 'all 0.15s',
              background: shadeMonth === m ? '#f59e0b' : 'var(--bg)',
              color:      shadeMonth === m ? 'white' : 'var(--text-secondary)',
            }}
          >
            {MONTH_LABELS[m]}
          </button>
        ))}
      </div>

      {/* ── 범례 + 통계 ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
        {shadeMonth === null ? (
          <div style={{ display: 'flex', gap: 14 }}>
            {[
              { color: BASE_COLOR.active.fill, stroke: BASE_COLOR.active.stroke, label: `설치 패널 (${stats.active_panels}매)` },
              { color: BASE_COLOR.shade.fill,  stroke: BASE_COLOR.shade.stroke,  label: `음영 구역 (${stats.shaded_panels}매)` },
            ].map(({ color, stroke, label }) => (
              <div key={label} className="legend-item">
                <div style={{ width: 16, height: 10, borderRadius: 2, background: color, border: `1.5px solid ${stroke}` }} />
                <span style={{ fontSize: 12 }}>{label}</span>
              </div>
            ))}
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>음영률:</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 11, color: shadeToColor(0) }}>0%</span>
              <svg width="80" height="10"><rect x="0" y="0" width="80" height="10" rx="3" fill="url(#shadGradLegend)"/><defs><linearGradient id="shadGradLegend" x1="0" x2="1"><stop offset="0%" stopColor={shadeToColor(0)}/><stop offset="50%" stopColor={shadeToColor(0.5)}/><stop offset="100%" stopColor={shadeToColor(1)}/></linearGradient></defs></svg>
              <span style={{ fontSize: 11, color: shadeToColor(1) }}>100%</span>
            </div>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>({MONTH_LABELS[shadeMonth]} 일 평균)</span>
          </div>
        )}

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { label: `${stats.row_count}행 × ${stats.col_count}열`, value: `총 ${stats.total_panels}매` },
            { label: '행 이격', value: `${stats.row_spacing_m}m` },
            { label: '최소 이격', value: `${stats.min_gap_m}m` },
          ].map(({ label, value }) => (
            <div key={label} style={{ textAlign: 'center', background: 'var(--bg)', borderRadius: 8, padding: '4px 10px' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 700 }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── SVG 배치도 ── */}
      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          style={{ width: '100%', height: 'auto', background: '#f0f4ff', borderRadius: 10, border: '1px solid var(--border)' }}
          aria-label="태양광 패널 배치도"
        >
          <GradientDef />

          {/* 지붕 윤곽 */}
          {roofPts && (
            <polygon points={roofPts} fill="rgba(241,245,249,0.9)" stroke="#a0aec0" strokeWidth="1.5" strokeDasharray="6,3" />
          )}

          {/* 패널 */}
          {panels.map((p) => {
            const key = `${p.row}-${p.col}`;
            const x = toX(p.lng);
            const y = toY(p.lat + ph);

            let fillColor, strokeColor;
            if (shadeMonth !== null && shadeMatrix) {
              const fraction = shadeMatrix[key] ?? 0;
              fillColor   = shadeToColor(fraction).replace('rgb(', 'rgba(').replace(')', ',0.8)');
              strokeColor = shadeToColor(fraction);
            } else {
              const c = BASE_COLOR[p.status] || BASE_COLOR.active;
              fillColor   = c.fill;
              strokeColor = c.stroke;
            }

            return (
              <rect
                key={key}
                x={x} y={y} width={pxW} height={pxH}
                fill={fillColor}
                stroke={strokeColor}
                strokeWidth="0.6"
                rx="1"
                style={{ cursor: 'pointer' }}
                onMouseEnter={(e) => {
                  const svgRect = e.currentTarget.closest('svg').getBoundingClientRect();
                  const fraction = shadeMatrix?.[key] ?? 0;
                  setTooltip({
                    x: e.clientX - svgRect.left + 12,
                    y: e.clientY - svgRect.top  - 48,
                    row: p.row + 1, col: p.col + 1,
                    kwh: p.kwh_year,
                    shade: Math.round(fraction * 100),
                    status: p.status,
                  });
                }}
                onMouseLeave={() => setTooltip(null)}
              />
            );
          })}

          {/* 나침반 */}
          <g transform={`translate(${SVG_W - 38}, ${PAD.top + 14})`}>
            <circle cx="0" cy="0" r="15" fill="white" stroke="#e2e8f0" strokeWidth="1" opacity="0.9" />
            <polygon points="0,-11 3,4 0,2 -3,4" fill="#1E6FD9" />
            <polygon points="0,11 3,-4 0,-2 -3,-4" fill="#cbd5e1" />
            <text y="-13" textAnchor="middle" fontSize="8" fontWeight="700" fill="#1E6FD9">N</text>
          </g>

          {/* 스케일바 */}
          <g transform={`translate(${PAD.left + 4}, ${SVG_H - 28})`}>
            <line x1="0" y1="0" x2={pxW * 5} y2="0" stroke="#718096" strokeWidth="1.5" />
            <line x1="0"        y1="-4" x2="0"        y2="4" stroke="#718096" strokeWidth="1.5" />
            <line x1={pxW * 5} y1="-4" x2={pxW * 5}  y2="4" stroke="#718096" strokeWidth="1.5" />
            <text x={pxW * 2.5} y="-8" textAnchor="middle" fontSize="10" fill="#718096">
              {(1.134 * 5).toFixed(1)}m
            </text>
          </g>

          {/* 방위 레이블 */}
          <text x={SVG_W / 2} y={PAD.top - 6} textAnchor="middle" fontSize="10" fill="#a0aec0">↑ 북</text>
          <text x={SVG_W / 2} y={SVG_H - 8}  textAnchor="middle" fontSize="10" fill="#a0aec0">↓ 남</text>
        </svg>

        {/* 툴팁 */}
        {tooltip && (
          <div style={{
            position: 'absolute', left: tooltip.x, top: tooltip.y,
            background: 'rgba(10,39,68,0.93)', color: 'white',
            borderRadius: 8, padding: '8px 14px', fontSize: 12,
            pointerEvents: 'none', whiteSpace: 'nowrap', zIndex: 20,
            boxShadow: '0 4px 20px rgba(0,0,0,0.35)',
          }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>
              패널 ({tooltip.row}행 {tooltip.col}열)
            </div>
            <div>연간 발전: <strong>{tooltip.kwh.toFixed(0)} kWh</strong></div>
            {shadeMonth !== null && (
              <div style={{ marginTop: 2 }}>
                음영률: <strong style={{ color: shadeToColor(tooltip.shade / 100) }}>{tooltip.shade}%</strong>
              </div>
            )}
            <div style={{ fontSize: 10, opacity: 0.7, marginTop: 3 }}>640W 모듈</div>
          </div>
        )}
      </div>

      {/* 하단 노트 */}
      <div className="notice-box" style={{ marginTop: 10, fontSize: 12 }}>
        ℹ️ 동지 고도각 기준 최소 이격 {stats.min_gap_m}m 적용
        {shadeMonth !== null && ` | ${MONTH_LABELS[shadeMonth]} 태양시 8h~16h 음영 시뮬레이션`}
      </div>
    </div>
  );
}

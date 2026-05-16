/**
 * PanelLayoutViewer
 * props:
 *   layout - panel_layout 객체 (pipeline.py 반환값)
 *     .panels         - [{row, col, lat, lng, status, kwh_year}]
 *     .roof_polygon   - [{lat, lng}]
 *     .panel_w_deg_lng - 패널 폭 (경도)
 *     .panel_h_deg_lat - 패널 높이 (위도)
 *     .stats          - {total_panels, active_panels, shaded_panels, row_count, col_count, ...}
 */

import { useState } from 'react';

const STATUS_COLOR = {
  active: { fill: 'rgba(30,111,217,0.65)', stroke: '#1565c0' },
  shade:  { fill: 'rgba(220,38,38,0.50)',  stroke: '#b91c1c' },
  buffer: { fill: 'rgba(160,174,192,0.40)', stroke: '#718096' },
};

const LEGEND = [
  { status: 'active', label: '설치 패널' },
  { status: 'shade',  label: '음영 구역' },
];

export default function PanelLayoutViewer({ layout }) {
  const [tooltip, setTooltip] = useState(null);

  if (!layout || !layout.panels || layout.panels.length === 0) return null;

  const { panels, roof_polygon, panel_w_deg_lng, panel_h_deg_lat, stats } = layout;

  // ── SVG 좌표계 계산 ──────────────────────────────────────────────────────
  const SVG_W = 620, SVG_H = 400;
  const PAD   = { top: 24, right: 24, bottom: 48, left: 24 };
  const drawW = SVG_W - PAD.left - PAD.right;
  const drawH = SVG_H - PAD.top  - PAD.bottom;

  // 바운딩박스 (roof_polygon 기준)
  const allLats = [...roof_polygon.map(p => p.lat), ...panels.map(p => p.lat), ...panels.map(p => p.lat + panel_h_deg_lat)];
  const allLngs = [...roof_polygon.map(p => p.lng), ...panels.map(p => p.lng), ...panels.map(p => p.lng + panel_w_deg_lng)];
  const minLat  = Math.min(...allLats), maxLat = Math.max(...allLats);
  const minLng  = Math.min(...allLngs), maxLng = Math.max(...allLngs);
  const latRange = maxLat - minLat || 1e-6;
  const lngRange = maxLng - minLng || 1e-6;

  // 위경도 → SVG 픽셀 (위도는 북=위 → y축 반전)
  const toX = (lng) => PAD.left  + ((lng  - minLng) / lngRange) * drawW;
  const toY = (lat) => PAD.top   + ((maxLat - lat)  / latRange) * drawH;

  // 지붕 폴리곤 포인트
  const roofPts = roof_polygon.map(p => `${toX(p.lng)},${toY(p.lat)}`).join(' ');

  // 패널 SVG 폭/높이 (픽셀)
  const pxW = Math.max(2, (panel_w_deg_lng  / lngRange) * drawW);
  const pxH = Math.max(2, (panel_h_deg_lat  / latRange) * drawH);

  return (
    <div className="chart-wrapper">
      {/* 범례 + 통계 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 16 }}>
          {LEGEND.map(({ status, label }) => (
            <div key={status} className="legend-item">
              <div style={{
                width: 16, height: 12, borderRadius: 2,
                background: STATUS_COLOR[status].fill,
                border: `1.5px solid ${STATUS_COLOR[status].stroke}`,
              }} />
              {label}
            </div>
          ))}
          <div className="legend-item" style={{ color: 'var(--text-muted)', fontSize: 11 }}>
            <div style={{ width: 16, height: 12, borderRadius: 2, border: '1.5px dashed #a0aec0', background: 'rgba(160,174,192,0.15)' }} />
            지붕 윤곽
          </div>
        </div>

        {/* 핵심 통계 */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {[
            { label: '총 패널', value: `${stats.total_panels}매`, color: 'var(--text-primary)' },
            { label: '설치 가능', value: `${stats.active_panels}매`, color: 'var(--blue)' },
            { label: '음영 구역', value: `${stats.shaded_panels}매`, color: '#dc2626' },
            { label: `${stats.row_count}행 × ${stats.col_count}열`, value: `이격 ${stats.row_spacing_m}m`, color: 'var(--text-muted)' },
          ].map(({ label, value, color }) => (
            <div key={label} style={{ textAlign: 'center', background: 'var(--bg)', borderRadius: 8, padding: '6px 12px', minWidth: 80 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* SVG 배치도 */}
      <div style={{ position: 'relative' }}>
        <svg
          viewBox={`0 0 ${SVG_W} ${SVG_H}`}
          style={{ width: '100%', height: 'auto', background: '#f8faff', borderRadius: 8, border: '1px solid var(--border)' }}
          aria-label="태양광 패널 배치도"
        >
          {/* 지붕 윤곽 (배경) */}
          <polygon
            points={roofPts}
            fill="rgba(241,245,249,0.9)"
            stroke="#a0aec0"
            strokeWidth="1.5"
            strokeDasharray="6,3"
          />

          {/* 버퍼 구역 (파라펫) — 지붕보다 약간 안쪽 표시 */}
          <polygon
            points={roofPts}
            fill="none"
            stroke="rgba(160,174,192,0.4)"
            strokeWidth="8"
          />

          {/* 패널 */}
          {panels.map((p, i) => {
            const x = toX(p.lng);
            const y = toY(p.lat + panel_h_deg_lat);  // y는 북쪽이 위
            const col = STATUS_COLOR[p.status] || STATUS_COLOR.active;
            return (
              <rect
                key={i}
                x={x} y={y} width={pxW} height={pxH}
                fill={col.fill}
                stroke={col.stroke}
                strokeWidth="0.5"
                style={{ cursor: p.status === 'active' ? 'pointer' : 'default' }}
                onMouseEnter={(e) => {
                  if (p.status !== 'active') return;
                  const rect = e.currentTarget.closest('svg').getBoundingClientRect();
                  setTooltip({
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top - 44,
                    row: p.row + 1, col: p.col + 1,
                    kwh: p.kwh_year,
                  });
                }}
                onMouseLeave={() => setTooltip(null)}
              />
            );
          })}

          {/* 행 이격 가이드라인 (첫 번째 행) */}
          {panels.length > 0 && stats.row_count > 1 && (() => {
            // 첫 행과 두 번째 행 사이 이격 공간 표시
            const firstRowPanels = panels.filter(p => p.row === 0);
            if (firstRowPanels.length === 0) return null;
            const topY = toY(firstRowPanels[0].lat + panel_h_deg_lat);
            const x1 = toX(firstRowPanels[0].lng);
            const x2 = toX(firstRowPanels[firstRowPanels.length - 1].lng + panel_w_deg_lng);
            return (
              <line x1={x1} y1={topY} x2={x2} y2={topY}
                stroke="#cbd5e1" strokeWidth="0.5" strokeDasharray="3,3" />
            );
          })()}

          {/* 나침반 (북쪽 화살표) */}
          <g transform={`translate(${SVG_W - 36}, ${PAD.top + 12})`}>
            <circle cx="0" cy="0" r="14" fill="white" stroke="#e2e8f0" strokeWidth="1" />
            <polygon points="0,-10 4,4 0,1 -4,4" fill="#1E6FD9" />
            <polygon points="0,10 4,-4 0,-1 -4,-4" fill="#cbd5e1" />
            <text y="-12" textAnchor="middle" fontSize="8" fontWeight="700" fill="#1E6FD9">N</text>
          </g>

          {/* 스케일바 */}
          <g transform={`translate(${PAD.left}, ${SVG_H - 20})`}>
            <line x1="0" y1="0" x2={pxW * 5} y2="0" stroke="#718096" strokeWidth="1.5" />
            <line x1="0" y1="-4" x2="0" y2="4" stroke="#718096" strokeWidth="1.5" />
            <line x1={pxW * 5} y1="-4" x2={pxW * 5} y2="4" stroke="#718096" strokeWidth="1.5" />
            <text x={pxW * 2.5} y="-6" textAnchor="middle" fontSize="9" fill="#718096">
              {(stats.panel_w_m * 5).toFixed(1)}m
            </text>
          </g>
        </svg>

        {/* 툴팁 */}
        {tooltip && (
          <div style={{
            position: 'absolute',
            left: tooltip.x + 12,
            top: tooltip.y,
            background: 'rgba(10,39,68,0.92)',
            color: 'white',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 12,
            pointerEvents: 'none',
            whiteSpace: 'nowrap',
            zIndex: 10,
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>패널 ({tooltip.row}행 {tooltip.col}열)</div>
            <div>연간 발전량: <strong>{tooltip.kwh.toFixed(0)} kWh</strong></div>
            <div style={{ fontSize: 10, opacity: 0.7, marginTop: 2 }}>640W 모듈</div>
          </div>
        )}
      </div>

      {/* 설계 노트 */}
      <div className="notice-box" style={{ marginTop: 12, fontSize: 12 }}>
        ℹ️ 동지({stats.tilt_deg}° 경사) 기준 최소 이격거리 {stats.min_gap_m}m 적용 — 음영 없는 최적 배치
      </div>
    </div>
  );
}

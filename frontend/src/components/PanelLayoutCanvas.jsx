/**
 * PanelLayoutCanvas — Canvas 2D 패널 배치도
 * - bounding box 격자 순회 + 중심점 PiP 필터로 패널 배치
 * - Canvas clip()으로 폴리곤 외부 픽셀 차단 (이중 보호)
 */
import { useEffect, useRef, useState } from 'react';

const M_PER_DEG_LAT = 111320;
const PAD = 44;

// Ray-casting Point-in-Polygon (px 좌표계)
function isInsidePolygon(point, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x, yi = polygon[i].y;
    const xj = polygon[j].x, yj = polygon[j].y;
    const intersect = ((yi > point.y) !== (yj > point.y))
      && (point.x < (xj - xi) * (point.y - yi) / (yj - yi) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function polygonPath(ctx, pts) {
  ctx.beginPath();
  pts.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
  ctx.closePath();
}

// draw() 반환값: 그려진 패널 수
function draw(canvas, layout) {
  if (!layout?.panels?.length) return 0;

  const ctx = canvas.getContext('2d');
  const { roof_polygon, panel_w_deg_lng: pw, panel_h_deg_lat: ph, stats } = layout;

  // ── 디버그: 폴리곤 좌표 확인 ─────────────────────────────────────────
  console.log('[PanelLayoutCanvas] roof_polygon 점 개수:', roof_polygon?.length);
  console.log('[PanelLayoutCanvas] roof_polygon 좌표:', JSON.stringify(roof_polygon));

  const CW = canvas.width, CH = canvas.height;
  const DW = CW - PAD * 2, DH = CH - PAD * 2;

  // ── 좌표 범위: roof_polygon 우선, 없으면 panels 사용 ──────────────────
  const srcPts = roof_polygon?.length
    ? roof_polygon
    : layout.panels.flatMap(p => p.corners?.length === 4
        ? p.corners
        : [{ lat: p.lat, lng: p.lng }, { lat: p.lat + ph, lng: p.lng + pw }]);

  const lats = srcPts.map(p => p.lat);
  const lngs = srcPts.map(p => p.lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const centerLat = (minLat + maxLat) / 2;
  const centerLng = (minLng + maxLng) / 2;

  // ── 등방 스케일 변환 ─────────────────────────────────────────────────
  const mPerDegLng = M_PER_DEG_LAT * Math.cos(centerLat * Math.PI / 180);
  const contentWm  = Math.max((maxLng - minLng) * mPerDegLng, 1e-3);
  const contentHm  = Math.max((maxLat - minLat) * M_PER_DEG_LAT, 1e-3);
  const scale = Math.min(DW / contentWm, DH / contentHm) * 0.82;

  const canvasCX = CW / 2, canvasCY = CH / 2;
  const toX = lng => canvasCX + (lng - centerLng) * mPerDegLng * scale;
  const toY = lat => canvasCY - (lat - centerLat) * M_PER_DEG_LAT * scale;

  // ── 지붕 폴리곤 픽셀 좌표 ────────────────────────────────────────────
  const roofPts = roof_polygon?.length >= 3
    ? roof_polygon.map(p => ({ x: toX(p.lng), y: toY(p.lat) }))
    : null;

  console.log('[PanelLayoutCanvas] roofPts (px):', JSON.stringify(roofPts));

  // ── 배경 ─────────────────────────────────────────────────────────────
  ctx.clearRect(0, 0, CW, CH);
  const grad = ctx.createLinearGradient(0, 0, CW, CH);
  grad.addColorStop(0, '#1a2a1a');
  grad.addColorStop(1, '#1a1a2e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CW, CH);

  // ── 지붕 면적 채우기 (연한 색) ───────────────────────────────────────
  if (roofPts) {
    polygonPath(ctx, roofPts);
    ctx.fillStyle = 'rgba(200,190,160,0.15)';
    ctx.fill();
  }

  // ── 패널 배치: bounding box 격자 순회 + 중심점 PiP ──────────────────
  const panelWpx = pw * mPerDegLng * scale;
  const panelHpx = ph * M_PER_DEG_LAT * scale;
  const gapPx    = Math.max(1, 0.1 * scale);
  const stepX    = panelWpx + gapPx;
  const stepY    = panelHpx + gapPx;

  const bboxMinX = roofPts ? Math.min(...roofPts.map(p => p.x)) : canvasCX - DW / 2;
  const bboxMaxX = roofPts ? Math.max(...roofPts.map(p => p.x)) : canvasCX + DW / 2;
  const bboxMinY = roofPts ? Math.min(...roofPts.map(p => p.y)) : canvasCY - DH / 2;
  const bboxMaxY = roofPts ? Math.max(...roofPts.map(p => p.y)) : canvasCY + DH / 2;

  ctx.save();
  // Canvas clip으로 폴리곤 외부 픽셀 차단 (이중 보호)
  if (roofPts) {
    polygonPath(ctx, roofPts);
    ctx.clip();
  }

  let drawnCount = 0;
  for (let py = bboxMinY; py + panelHpx <= bboxMaxY + gapPx; py += stepY) {
    for (let px = bboxMinX; px + panelWpx <= bboxMaxX + gapPx; px += stepX) {
      // 중심점 기준 PiP 판별
      const centerX = px + panelWpx / 2;
      const centerY = py + panelHpx / 2;
      if (roofPts && !isInsidePolygon({ x: centerX, y: centerY }, roofPts)) continue;

      // 패널 채우기
      ctx.fillStyle   = 'rgba(37,99,235,0.85)';
      ctx.strokeStyle = 'rgba(147,197,253,0.85)';
      ctx.lineWidth   = 0.6;
      ctx.fillRect(px, py, panelWpx, panelHpx);
      ctx.strokeRect(px, py, panelWpx, panelHpx);

      // 패널 중앙 세로 구분선 (셀 느낌)
      ctx.strokeStyle = 'rgba(147,197,253,0.2)';
      ctx.lineWidth   = 0.35;
      ctx.beginPath();
      ctx.moveTo(px + panelWpx / 2, py);
      ctx.lineTo(px + panelWpx / 2, py + panelHpx);
      ctx.stroke();

      drawnCount++;
    }
  }

  ctx.restore();
  console.log('[PanelLayoutCanvas] 그려진 패널:', drawnCount, '/ 총 용량:', (drawnCount * 0.64).toFixed(1), 'kW');

  // ── 지붕 외곽선 (패널 위에 그려서 z-order 확보) ──────────────────────
  if (roofPts) {
    polygonPath(ctx, roofPts);
    ctx.strokeStyle = '#FFD700';
    ctx.lineWidth   = 2.5;
    ctx.setLineDash([]);
    ctx.stroke();

    roofPts.forEach(pt => {
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#FFD700';
      ctx.fill();
    });
  }

  // ── 방위 레이블 ──────────────────────────────────────────────────────
  ctx.font = 'bold 11px "Noto Sans KR", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.5)';
  ctx.fillText('↑ 북', CW / 2, 20);
  ctx.fillText('↓ 남', CW / 2, CH - 8);

  // ── 나침반 (우상단) ──────────────────────────────────────────────────
  const ncx = CW - 30, ncy = 30, nr = 14;
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.beginPath(); ctx.arc(ncx, ncy, nr, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.2)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = '#60a5fa';
  ctx.beginPath();
  ctx.moveTo(ncx, ncy - nr + 2); ctx.lineTo(ncx + 3.5, ncy + 1);
  ctx.lineTo(ncx, ncy - 1);      ctx.lineTo(ncx - 3.5, ncy + 1);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#374151';
  ctx.beginPath();
  ctx.moveTo(ncx, ncy + nr - 2); ctx.lineTo(ncx + 3.5, ncy - 1);
  ctx.lineTo(ncx, ncy + 1);      ctx.lineTo(ncx - 3.5, ncy - 1);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#93c5fd';
  ctx.font = 'bold 7px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('N', ncx, ncy - nr - 3);

  // ── 방위각 화살표 ────────────────────────────────────────────────────
  const az    = stats?.azimuth_deg ?? 180;
  const azRad = az * Math.PI / 180;
  const aLen  = 20;
  ctx.strokeStyle = '#f87171';
  ctx.lineWidth   = 1.8;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(ncx, ncy);
  ctx.lineTo(ncx + aLen * Math.sin(azRad), ncy - aLen * Math.cos(azRad));
  ctx.stroke();
  ctx.setLineDash([]);

  // ── 스케일바 (좌하단) ────────────────────────────────────────────────
  const scaleM  = 5;
  const scalePx = scaleM * scale;
  const sbX = PAD + 4, sbY = CH - 14;
  ctx.strokeStyle = 'rgba(255,255,255,0.7)';
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  ctx.moveTo(sbX, sbY);              ctx.lineTo(sbX + scalePx, sbY);
  ctx.moveTo(sbX, sbY - 4);          ctx.lineTo(sbX, sbY + 4);
  ctx.moveTo(sbX + scalePx, sbY - 4); ctx.lineTo(sbX + scalePx, sbY + 4);
  ctx.stroke();
  ctx.fillStyle   = 'rgba(255,255,255,0.7)';
  ctx.font        = '10px sans-serif';
  ctx.textAlign   = 'center';
  ctx.fillText(`${scaleM}m`, sbX + scalePx / 2, sbY - 6);

  // ── 통계 오버레이 (우하단) ───────────────────────────────────────────
  const totalKw = (drawnCount * 0.64).toFixed(1);
  const oW = 118, oH = 60;
  const oX = CW - PAD - 4, oY = CH - PAD - 4;

  ctx.fillStyle = 'rgba(0,0,0,0.65)';
  if (ctx.roundRect) {
    ctx.beginPath();
    ctx.roundRect(oX - oW, oY - oH, oW, oH, 8);
    ctx.fill();
  } else {
    ctx.fillRect(oX - oW, oY - oH, oW, oH);
  }
  const omX = oX - oW / 2;
  ctx.textAlign   = 'center';
  ctx.fillStyle   = 'white';
  ctx.font        = 'bold 17px sans-serif';
  ctx.fillText(`${drawnCount}매`, omX, oY - oH + 26);
  ctx.fillStyle   = '#93c5fd';
  ctx.font        = '12px sans-serif';
  ctx.fillText(`${totalKw} kW`, omX, oY - oH + 46);

  return drawnCount;
}

// ────────────────────────────────────────────────────────────────────────────

export default function PanelLayoutCanvas({ layout }) {
  const canvasRef  = useRef(null);
  const [drawn, setDrawn] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout?.panels?.length) return;
    const count = draw(canvas, layout);
    setDrawn(count ?? 0);
  }, [layout]);

  if (!layout?.panels?.length) return null;
  const { stats } = layout;

  return (
    <div className="chart-wrapper">
      {/* 범례 + 통계 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexWrap: 'wrap', gap: 8, marginBottom: 10,
      }}>
        <div style={{ display: 'flex', gap: 14 }}>
          {[
            { fill: 'rgba(37,99,235,0.85)',  stroke: '#93c5fd', label: `설치 패널 (${drawn}매)` },
            { fill: 'transparent',           stroke: '#FFD700', dash: true, label: '지붕 외곽선' },
          ].map(({ fill, stroke, label, dash }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 20, height: 11, borderRadius: 2,
                background: fill,
                border: `2px ${dash ? 'solid' : 'solid'} ${stroke}`,
              }} />
              <span style={{ fontSize: 12 }}>{label}</span>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { label: '설치 용량',  value: `${(drawn * 0.64).toFixed(1)} kW` },
            { label: '행 이격',    value: `${stats?.row_spacing_m ?? '-'}m` },
            { label: '최소 이격',  value: `${stats?.min_gap_m ?? '-'}m` },
          ].map(({ label, value }) => (
            <div key={label} style={{
              textAlign: 'center', background: 'var(--bg)',
              borderRadius: 8, padding: '4px 10px',
            }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 700 }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      <canvas
        ref={canvasRef}
        width={640}
        height={440}
        style={{
          width: '100%', height: 'auto',
          borderRadius: 12, border: '1px solid var(--border)',
          display: 'block', background: '#1a1a2e',
        }}
        aria-label="태양광 패널 배치도"
      />

      <div className="notice-box" style={{ marginTop: 10, fontSize: 12 }}>
        💛 노란 외곽선 = 지붕 폴리곤 (방위각 {stats?.azimuth_deg ?? 180}° 적용)
        · 격자 순회 + 중심점 PiP로 외곽선 내부 패널만 표시
        · 실제 배치 {drawn}매 × 0.64kW = {(drawn * 0.64).toFixed(1)} kW
      </div>
    </div>
  );
}

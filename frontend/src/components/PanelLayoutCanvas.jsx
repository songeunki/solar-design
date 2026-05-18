/**
 * PanelLayoutCanvas — Canvas 2D 패널 배치도
 * - 지붕 폴리곤을 클리핑 영역으로 사용
 * - 패널은 corners(방위각 회전 적용) 기준으로 렌더링
 * - Ray-casting Point-in-Polygon으로 외부 패널 안전 필터링
 */
import { useEffect, useRef } from 'react';

const M_PER_DEG_LAT = 111320;
const PAD = 44;

// Ray-casting 알고리즘 (px 좌표계)
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

// 캔버스 경로: polygon 픽셀 좌표 배열로 path 설정
function polygonPath(ctx, pts) {
  ctx.beginPath();
  pts.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
  ctx.closePath();
}

function draw(canvas, layout) {
  if (!layout?.panels?.length) return;
  const ctx = canvas.getContext('2d');
  const { panels, roof_polygon, panel_w_deg_lng: pw, panel_h_deg_lat: ph, stats } = layout;

  const CW = canvas.width, CH = canvas.height;
  const DW = CW - PAD * 2, DH = CH - PAD * 2;

  // ── 좌표 범위 계산 ──────────────────────────────────────────────────────
  const lats = [], lngs = [];
  panels.forEach(p => {
    if (p.corners?.length === 4) {
      p.corners.forEach(c => { lats.push(c.lat); lngs.push(c.lng); });
    } else {
      lats.push(p.lat, p.lat + ph);
      lngs.push(p.lng, p.lng + pw);
    }
  });
  roof_polygon?.forEach(p => { lats.push(p.lat); lngs.push(p.lng); });

  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const centerLat = (minLat + maxLat) / 2;
  const centerLng = (minLng + maxLng) / 2;

  // ── 위경도 → px 변환 (등방 스케일) ────────────────────────────────────
  const mPerDegLng = M_PER_DEG_LAT * Math.cos(centerLat * Math.PI / 180);
  const contentWm  = Math.max((maxLng - minLng) * mPerDegLng, 1e-3);
  const contentHm  = Math.max((maxLat - minLat) * M_PER_DEG_LAT, 1e-3);
  const scale = Math.min(DW / contentWm, DH / contentHm) * 0.85;

  const cx = CW / 2, cy = CH / 2;
  const toX = lng => cx + (lng - centerLng) * mPerDegLng * scale;
  const toY = lat => cy - (lat - centerLat) * M_PER_DEG_LAT * scale;

  // ── 패널 px 꼭짓점 계산 ──────────────────────────────────────────────
  const panelPxPts = (p) => {
    if (p.corners?.length === 4) {
      return p.corners.map(c => ({ x: toX(c.lng), y: toY(c.lat) }));
    }
    // corners 없을 때 축-정렬 폴백
    return [
      { x: toX(p.lng),      y: toY(p.lat) },
      { x: toX(p.lng + pw), y: toY(p.lat) },
      { x: toX(p.lng + pw), y: toY(p.lat + ph) },
      { x: toX(p.lng),      y: toY(p.lat + ph) },
    ];
  };

  // ── 지붕 폴리곤 px 좌표 ───────────────────────────────────────────────
  const roofPts = roof_polygon?.length >= 3
    ? roof_polygon.map(p => ({ x: toX(p.lng), y: toY(p.lat) }))
    : null;

  // ════════════════════════════════════════════
  // 렌더링 시작
  // ════════════════════════════════════════════

  // 배경 (위성사진 느낌)
  ctx.clearRect(0, 0, CW, CH);
  const grad = ctx.createLinearGradient(0, 0, CW, CH);
  grad.addColorStop(0, '#1a2a1a');
  grad.addColorStop(1, '#1a1a2e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, CW, CH);

  // 지붕 면적 채우기
  if (roofPts) {
    polygonPath(ctx, roofPts);
    ctx.fillStyle = 'rgba(200, 190, 160, 0.18)';
    ctx.fill();
  }

  // ── 패널 렌더링 (폴리곤 클리핑 적용) ────────────────────────────────
  ctx.save();

  if (roofPts) {
    // 캔버스 클리핑 → 폴리곤 바깥 픽셀 자동 차단
    polygonPath(ctx, roofPts);
    ctx.clip();
  }

  const activePanels = panels.filter(p => p.status !== 'buffer');

  activePanels.forEach(p => {
    const pts = panelPxPts(p);

    // Point-in-Polygon 안전 필터: 패널 중심이 폴리곤 안에 있는지 확인
    if (roofPts) {
      const midX = pts.reduce((s, pt) => s + pt.x, 0) / pts.length;
      const midY = pts.reduce((s, pt) => s + pt.y, 0) / pts.length;
      if (!isInsidePolygon({ x: midX, y: midY }, roofPts)) return;
    }

    const isShade = p.status === 'shade';
    polygonPath(ctx, pts);
    ctx.fillStyle   = isShade ? 'rgba(239,68,68,0.80)'  : 'rgba(37,99,235,0.85)';
    ctx.fill();
    ctx.strokeStyle = isShade ? 'rgba(252,165,165,0.9)' : 'rgba(147,197,253,0.9)';
    ctx.lineWidth   = 0.6;
    ctx.stroke();

    // 패널 내부 가이드라인 (셀 구분선)
    if (pts.length === 4) {
      const [sw, se, ne, nw] = pts;
      const midT = { x: (nw.x + ne.x) / 2, y: (nw.y + ne.y) / 2 };
      const midB = { x: (sw.x + se.x) / 2, y: (sw.y + se.y) / 2 };
      ctx.strokeStyle = isShade ? 'rgba(252,165,165,0.3)' : 'rgba(147,197,253,0.3)';
      ctx.lineWidth = 0.4;
      ctx.beginPath();
      ctx.moveTo(midT.x, midT.y);
      ctx.lineTo(midB.x, midB.y);
      ctx.stroke();
    }
  });

  ctx.restore();

  // ── 지붕 외곽선 (패널 위에 그려서 경계 명확히) ──────────────────────
  if (roofPts) {
    polygonPath(ctx, roofPts);
    ctx.strokeStyle = '#FFD700';
    ctx.lineWidth   = 2.5;
    ctx.setLineDash([]);
    ctx.stroke();

    // 모서리 점
    roofPts.forEach(pt => {
      ctx.beginPath();
      ctx.arc(pt.x, pt.y, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#FFD700';
      ctx.fill();
    });
  }

  // ── 방위 레이블 ──────────────────────────────────────────────────────
  ctx.font = 'bold 11px "Noto Sans KR", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.55)';
  ctx.fillText('↑ 북', CW / 2, 20);
  ctx.fillText('↓ 남', CW / 2, CH - 8);

  // ── 나침반 (우상단) ──────────────────────────────────────────────────
  const ncx = CW - 28, ncy = 28, nr = 14;
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.beginPath(); ctx.arc(ncx, ncy, nr, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.25)'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = '#60a5fa';
  ctx.beginPath();
  ctx.moveTo(ncx, ncy - nr + 2);
  ctx.lineTo(ncx + 3.5, ncy + 1);
  ctx.lineTo(ncx, ncy - 1);
  ctx.lineTo(ncx - 3.5, ncy + 1);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#374151';
  ctx.beginPath();
  ctx.moveTo(ncx, ncy + nr - 2);
  ctx.lineTo(ncx + 3.5, ncy - 1);
  ctx.lineTo(ncx, ncy + 1);
  ctx.lineTo(ncx - 3.5, ncy - 1);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#93c5fd';
  ctx.font = 'bold 7px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('N', ncx, ncy - nr - 3);

  // ── 방위각 화살표 ────────────────────────────────────────────────────
  const az    = stats?.azimuth_deg ?? 180;
  const azRad = az * Math.PI / 180;
  const aLen  = 22;
  ctx.strokeStyle = '#f87171';
  ctx.lineWidth = 1.8;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(ncx, ncy);
  ctx.lineTo(ncx + aLen * Math.sin(azRad), ncy - aLen * Math.cos(azRad));
  ctx.stroke();
  ctx.setLineDash([]);

  // ── 스케일바 (좌하단) ──────────────────────────────────────────────
  const scaleM   = 5;
  const scalePx  = scaleM * scale;
  const sbX = PAD + 4, sbY = CH - 14;
  ctx.strokeStyle = 'rgba(255,255,255,0.75)';
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(sbX, sbY);             ctx.lineTo(sbX + scalePx, sbY);
  ctx.moveTo(sbX, sbY - 4);         ctx.lineTo(sbX, sbY + 4);
  ctx.moveTo(sbX + scalePx, sbY-4); ctx.lineTo(sbX + scalePx, sbY+4);
  ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.75)';
  ctx.font = '10px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`${scaleM}m`, sbX + scalePx / 2, sbY - 6);

  // ── 통계 오버레이 (우하단) ───────────────────────────────────────────
  const installedCnt = activePanels.filter(p => p.status !== 'shade').length;
  const totalKw      = (installedCnt * 0.64).toFixed(1);
  const oW = 116, oH = 58;
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
  ctx.textAlign = 'center';
  ctx.fillStyle = 'white';
  ctx.font = 'bold 16px sans-serif';
  ctx.fillText(`${installedCnt}매`, omX, oY - oH + 24);
  ctx.fillStyle = '#93c5fd';
  ctx.font = '12px sans-serif';
  ctx.fillText(`${totalKw} kW`, omX, oY - oH + 44);
}

export default function PanelLayoutCanvas({ layout }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout?.panels?.length) return;
    draw(canvas, layout);
  }, [layout]);

  if (!layout?.panels?.length) return null;
  const { stats } = layout;
  const activeCnt = (layout.panels || []).filter(p => p.status === 'active' || p.status === 'north').length;

  return (
    <div className="chart-wrapper">
      {/* 범례 + 통계 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexWrap: 'wrap', gap: 8, marginBottom: 10,
      }}>
        <div style={{ display: 'flex', gap: 14 }}>
          {[
            { fill: 'rgba(37,99,235,0.85)',  stroke: '#93c5fd', label: `설치 패널 (${stats.active_panels ?? activeCnt}매)` },
            { fill: 'rgba(239,68,68,0.80)',  stroke: '#fca5a5', label: `음영 구역 (${stats.shaded_panels ?? 0}매)` },
            { fill: 'transparent',           stroke: '#FFD700', label: '지붕 외곽선', dash: true },
          ].map(({ fill, stroke, label, dash }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 20, height: 11, borderRadius: 2,
                background: fill,
                border: `2px ${dash ? 'dashed' : 'solid'} ${stroke}`,
              }} />
              <span style={{ fontSize: 12 }}>{label}</span>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { label: `${stats.row_count ?? '-'}행 × ${stats.col_count ?? '-'}열`, value: `총 ${stats.total_panels ?? '-'}매` },
            { label: '행 이격',   value: `${stats.row_spacing_m ?? '-'}m` },
            { label: '설치 용량', value: `${((stats.active_panels ?? activeCnt) * 0.64).toFixed(1)} kW` },
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
        💛 노란 외곽선 = 지붕 폴리곤 (방위각 {stats?.azimuth_deg ?? 180}° 회전 적용)
        · 파란 패널 = 설치 가능 · 빨간 패널 = 음영 구역
        · 외곽선 외부 패널은 자동 제외
      </div>
    </div>
  );
}

/**
 * PanelLayoutCanvas — Canvas 2D 패널 배치도 (대안 A)
 * Three.js 없이 순수 Canvas API로 안정적으로 렌더링
 */
import { useEffect, useRef } from 'react';

const ACTIVE_FILL   = 'rgba(30,111,217,0.65)';
const ACTIVE_STROKE = '#1565c0';
const SHADE_FILL    = 'rgba(220,38,38,0.50)';
const SHADE_STROKE  = '#b91c1c';
const PAD           = 36;

const M_PER_DEG_LAT = 111320;

function draw(canvas, layout) {
  const ctx = canvas.getContext('2d');
  const { panels, roof_polygon, panel_w_deg_lng: pw, panel_h_deg_lat: ph, stats } = layout;

  const CW = canvas.width, CH = canvas.height;
  const DW = CW - PAD * 2, DH = CH - PAD * 2;

  // 전체 좌표 범위 계산
  const lats = panels.flatMap(p => [p.lat, p.lat + ph]);
  const lngs = panels.flatMap(p => [p.lng, p.lng + pw]);
  if (roof_polygon?.length) {
    lats.push(...roof_polygon.map(p => p.lat));
    lngs.push(...roof_polygon.map(p => p.lng));
  }
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);

  // 중심 좌표 (등방 스케일 기준점)
  const centerLat = (minLat + maxLat) / 2;
  const centerLng = (minLng + maxLng) / 2;

  // 위경도 → 미터 변환 계수 (위도에 따른 경도 왜곡 보정)
  const mPerDegLng = M_PER_DEG_LAT * Math.cos(centerLat * Math.PI / 180);

  // 콘텐츠 크기(미터) → 캔버스에 꽉 차게 맞추는 단일 스케일
  const contentWm = (maxLng - minLng) * mPerDegLng || 1e-3;
  const contentHm = (maxLat - minLat) * M_PER_DEG_LAT || 1e-3;
  const scale = Math.min(DW / contentWm, DH / contentHm) * 0.92; // 여유 8%

  // 캔버스 중앙 기준 좌표 변환
  const canvasCX = CW / 2;
  const canvasCY = CH / 2;
  const toX = lng => canvasCX + (lng - centerLng) * mPerDegLng * scale;
  const toY = lat => canvasCY - (lat - centerLat) * M_PER_DEG_LAT * scale; // Y축 반전
  const pxW = Math.max(3, pw * mPerDegLng * scale);
  const pxH = Math.max(3, ph * M_PER_DEG_LAT * scale);

  // 배경
  ctx.clearRect(0, 0, CW, CH);
  ctx.fillStyle = '#f0f4ff';
  ctx.roundRect ? ctx.roundRect(0, 0, CW, CH, 10) : ctx.fillRect(0, 0, CW, CH);
  ctx.fill();

  // 지붕 윤곽
  if (roof_polygon?.length >= 3) {
    ctx.beginPath();
    roof_polygon.forEach((p, i) =>
      i === 0 ? ctx.moveTo(toX(p.lng), toY(p.lat)) : ctx.lineTo(toX(p.lng), toY(p.lat))
    );
    ctx.closePath();
    ctx.fillStyle = 'rgba(241,245,249,0.9)';
    ctx.fill();
    ctx.strokeStyle = '#a0aec0';
    ctx.setLineDash([6, 3]);
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // 패널 렌더링
  panels.forEach(p => {
    if (p.status === 'buffer') return;
    const x = toX(p.lng);
    const y = toY(p.lat + ph);
    const isShade = p.status === 'shade';
    ctx.fillStyle   = isShade ? SHADE_FILL   : ACTIVE_FILL;
    ctx.strokeStyle = isShade ? SHADE_STROKE : ACTIVE_STROKE;
    ctx.lineWidth   = 0.7;
    ctx.fillRect(x, y, pxW, pxH);
    ctx.strokeRect(x, y, pxW, pxH);
  });

  // 방위 레이블
  ctx.fillStyle = '#94a3b8';
  ctx.font = 'bold 11px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('↑ 북', CW / 2, PAD - 14);
  ctx.fillText('↓ 남', CW / 2, CH - 8);

  // 방위각 화살표
  const { azimuth_deg: az = 180 } = stats;
  const cx = CW / 2, cy = CH / 2, arrowLen = 34;
  const azRad = az * Math.PI / 180;
  const ex = cx + arrowLen * Math.sin(azRad);
  const ey = cy - arrowLen * Math.cos(azRad);
  ctx.strokeStyle = '#dc2626';
  ctx.lineWidth = 2;
  ctx.setLineDash([4, 2]);
  ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(ex, ey); ctx.stroke();
  ctx.setLineDash([]);
  // 화살촉
  const hAngle = 0.35;
  ctx.fillStyle = '#dc2626';
  ctx.beginPath();
  ctx.moveTo(ex, ey);
  ctx.lineTo(ex - 8 * Math.sin(azRad - hAngle), ey + 8 * Math.cos(azRad - hAngle));
  ctx.lineTo(ex - 8 * Math.sin(azRad + hAngle), ey + 8 * Math.cos(azRad + hAngle));
  ctx.closePath(); ctx.fill();
  // 방위각 텍스트
  ctx.fillStyle = '#dc2626';
  ctx.font = 'bold 9px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`${az}°`, cx, cy - 6);

  // 나침반 (우상단)
  const cx2 = CW - PAD + 4, cy2 = PAD + 10, r = 13;
  ctx.fillStyle = 'rgba(255,255,255,0.9)';
  ctx.beginPath(); ctx.arc(cx2, cy2, r, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = '#e2e8f0'; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = '#1E6FD9';
  ctx.beginPath(); ctx.moveTo(cx2, cy2 - r + 2); ctx.lineTo(cx2 + 3, cy2 + 2); ctx.lineTo(cx2, cy2); ctx.lineTo(cx2 - 3, cy2 + 2); ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#cbd5e1';
  ctx.beginPath(); ctx.moveTo(cx2, cy2 + r - 2); ctx.lineTo(cx2 + 3, cy2 - 2); ctx.lineTo(cx2, cy2); ctx.lineTo(cx2 - 3, cy2 - 2); ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#1E6FD9'; ctx.font = 'bold 7px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('N', cx2, cy2 - r - 3);

  // 스케일바
  const scaleLen = pxW * 5;
  const sbX = PAD + 4, sbY = CH - 14;
  ctx.strokeStyle = '#718096'; ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(sbX, sbY);           ctx.lineTo(sbX + scaleLen, sbY);
  ctx.moveTo(sbX, sbY - 4);       ctx.lineTo(sbX, sbY + 4);
  ctx.moveTo(sbX + scaleLen, sbY - 4); ctx.lineTo(sbX + scaleLen, sbY + 4);
  ctx.stroke();
  ctx.fillStyle = '#718096'; ctx.font = '10px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText(`${(1.134 * 5).toFixed(1)}m`, sbX + scaleLen / 2, sbY - 6);
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

  return (
    <div className="chart-wrapper">
      {/* 범례 + 통계 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
        <div style={{ display: 'flex', gap: 14 }}>
          {[
            { fill: ACTIVE_FILL, stroke: ACTIVE_STROKE, label: `설치 패널 (${stats.active_panels}매)` },
            { fill: SHADE_FILL,  stroke: SHADE_STROKE,  label: `음영 구역 (${stats.shaded_panels}매)` },
          ].map(({ fill, stroke, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 16, height: 10, borderRadius: 2, background: fill, border: `1.5px solid ${stroke}` }} />
              <span style={{ fontSize: 12 }}>{label}</span>
            </div>
          ))}
        </div>
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

      <canvas
        ref={canvasRef}
        width={620}
        height={420}
        style={{ width: '100%', height: 'auto', borderRadius: 10, border: '1px solid var(--border)', display: 'block' }}
        aria-label="태양광 패널 배치도"
      />

      <div className="notice-box" style={{ marginTop: 10, fontSize: 12 }}>
        ℹ️ 동지 고도각 기준 최소 이격 {stats.min_gap_m}m 적용 · 빨간 화살표 = 패널 방위각 {stats.azimuth_deg ?? 180}°
      </div>
    </div>
  );
}

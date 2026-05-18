/**
 * PanelLayoutCanvas — Turf.js 기반 정확한 폴리곤 내부 패널 배치
 *
 * 핵심 수정:
 *   - bbox를 roof_polygon 좌표만으로 계산 (panel corners 제외)
 *     → 이전 버전은 panel.lat+ph 등 축-정렬 범위를 포함해 회전 건물에서 bbox가
 *       실제 지붕보다 훨씬 커졌고, 이것이 폴리곤이 삼각형처럼 보이게 만든 원인.
 *   - Mercator 위도 보정 포함 등방 스케일 변환
 *   - Turf.js booleanPointInPolygon 으로 PiP 판별
 *   - 패널 corners(방위각 회전 적용) 사용, 없으면 fillRect 폴백
 */
import { useEffect, useRef, useState } from 'react';
import { polygon as turfPolygon, point as turfPoint, booleanPointInPolygon } from '@turf/turf';

const M_PER_DEG_LAT = 111320;
const PAD            = 44;

// ── Mercator 투영 기반 위경도 → Canvas px 변환 ──────────────────────────────
// bbox: { minLat, maxLat, minLng, maxLng }  (roof_polygon 좌표만으로 구성)
function lngLatToCanvas(lng, lat, bbox, cW, cH, pad = PAD) {
  const centerLat = (bbox.minLat + bbox.maxLat) / 2;
  const centerLng = (bbox.minLng + bbox.maxLng) / 2;

  // 위도 1도 ≈ 111320m, 경도 1도 ≈ 111320 × cos(lat) m
  const mPerDegLng = M_PER_DEG_LAT * Math.cos(centerLat * Math.PI / 180);

  // 실제 콘텐츠 크기(미터) → 캔버스 드로잉 영역에 맞는 등방 스케일
  const DW = cW - pad * 2;
  const DH = cH - pad * 2;
  const contentWm = Math.max((bbox.maxLng - bbox.minLng) * mPerDegLng, 1e-3);
  const contentHm = Math.max((bbox.maxLat - bbox.minLat) * M_PER_DEG_LAT,  1e-3);
  const scale = Math.min(DW / contentWm, DH / contentHm) * 0.83;

  return {
    x: cW / 2 + (lng - centerLng) * mPerDegLng * scale,
    y: cH / 2 - (lat - centerLat) * M_PER_DEG_LAT * scale,
  };
}

// ── 메인 draw 함수 ────────────────────────────────────────────────────────────
function draw(canvas, layout, onPanelCountChange) {
  if (!canvas || !layout?.panels?.length) return 0;

  const ctx = canvas.getContext('2d');
  const {
    panels,
    roof_polygon,
    panel_w_deg_lng: pw,
    panel_h_deg_lat: ph,
    stats,
  } = layout;

  // ── 디버그: 폴리곤 좌표 확인 ─────────────────────────────────────────────
  console.log('[PanelLayoutCanvas] roof_polygon 점 개수:', roof_polygon?.length);
  console.log('[PanelLayoutCanvas] roof_polygon:', JSON.stringify(roof_polygon));
  console.log('[PanelLayoutCanvas] panels 총수:', panels?.length,
    '/ active:', panels?.filter(p => p.status !== 'buffer').length);

  const CW = canvas.width, CH = canvas.height;

  // ── roof_polygon 없거나 점이 부족하면 panel 좌표에서 폴백 생성 ──────────
  let effectivePolygon = roof_polygon;
  if (!effectivePolygon || effectivePolygon.length < 3) {
    console.warn('[PanelLayoutCanvas] roof_polygon 부족 — 패널 bounding box 폴백');
    const allLats = panels.flatMap(p => p.corners?.length
      ? p.corners.map(c => c.lat)
      : [p.lat, p.lat + ph]);
    const allLngs = panels.flatMap(p => p.corners?.length
      ? p.corners.map(c => c.lng)
      : [p.lng, p.lng + pw]);
    const minLat = Math.min(...allLats), maxLat = Math.max(...allLats);
    const minLng = Math.min(...allLngs), maxLng = Math.max(...allLngs);
    effectivePolygon = [
      { lat: minLat, lng: minLng },
      { lat: minLat, lng: maxLng },
      { lat: maxLat, lng: maxLng },
      { lat: maxLat, lng: minLng },
    ];
  }
  const roof_polygon_eff = effectivePolygon;

  // ── bbox: roof_polygon 좌표만으로 계산 (panel corners 제외) ──────────────
  const rLats = roof_polygon_eff.map(p => p.lat);
  const rLngs = roof_polygon_eff.map(p => p.lng);
  const bbox = {
    minLat: Math.min(...rLats), maxLat: Math.max(...rLats),
    minLng: Math.min(...rLngs), maxLng: Math.max(...rLngs),
  };

  // ── 좌표 변환 헬퍼 ───────────────────────────────────────────────────────
  const toC = (lng, lat) => lngLatToCanvas(lng, lat, bbox, CW, CH, PAD);

  // ── Turf.js 폴리곤 생성 (PiP 판별용) ────────────────────────────────────
  const roofCoords = [
    ...roof_polygon_eff.map(p => [p.lng, p.lat]),
    [roof_polygon_eff[0].lng, roof_polygon_eff[0].lat], // GeoJSON 닫기
  ];
  const turfRoof = turfPolygon([roofCoords]);

  // ── 지붕 폴리곤 Canvas px 좌표 (raw) ────────────────────────────────────
  const roofPtsRaw = roof_polygon_eff.map(p => toC(p.lng, p.lat));

  // ── 중앙 정렬 offset 계산 ─────────────────────────────────────────────────
  // 변환된 폴리곤 무게중심 → Canvas 정중앙으로 이동
  const avgX    = roofPtsRaw.reduce((s, p) => s + p.x, 0) / roofPtsRaw.length;
  const avgY    = roofPtsRaw.reduce((s, p) => s + p.y, 0) / roofPtsRaw.length;
  const offsetX = CW / 2 - avgX;
  const offsetY = CH / 2 - avgY;
  const shift       = pt => ({ x: pt.x + offsetX, y: pt.y + offsetY });
  const toCShifted  = (lng, lat) => shift(toC(lng, lat));

  // offset 적용된 최종 폴리곤 좌표
  const roofPts = roofPtsRaw.map(shift);
  console.log('[PanelLayoutCanvas] offset (px):', offsetX.toFixed(1), offsetY.toFixed(1));
  console.log('[PanelLayoutCanvas] roofPts (중앙정렬 후):', JSON.stringify(roofPts));

  // ════════════════════════════════════════════════════════════════════════
  // 렌더링
  // ════════════════════════════════════════════════════════════════════════

  // 배경
  ctx.clearRect(0, 0, CW, CH);
  const bg = ctx.createLinearGradient(0, 0, CW, CH);
  bg.addColorStop(0, '#1a2a1a');
  bg.addColorStop(1, '#1a1a2e');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, CW, CH);

  // 지붕 면적 (연한 배경)
  ctx.beginPath();
  roofPts.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
  ctx.closePath();
  ctx.fillStyle = 'rgba(200,190,160,0.15)';
  ctx.fill();

  // ── 패널 렌더링 ─────────────────────────────────────────────────────────
  ctx.save();

  // Canvas clip: 폴리곤 외부 픽셀 물리적 차단
  ctx.beginPath();
  roofPts.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
  ctx.closePath();
  ctx.clip();

  let drawnCount = 0;
  const activePanels = panels.filter(p => p.status !== 'buffer');

  activePanels.forEach(p => {
    // Turf.js PiP: 패널 중심이 지붕 폴리곤 안에 있는지 확인
    const centerLng = p.lng + pw / 2;
    const centerLat = p.lat + ph / 2;
    if (!booleanPointInPolygon(turfPoint([centerLng, centerLat]), turfRoof)) return;

    const isShade = p.status === 'shade';
    ctx.fillStyle   = isShade ? 'rgba(239,68,68,0.80)'   : 'rgba(59,130,246,0.85)';
    ctx.strokeStyle = isShade ? 'rgba(252,165,165,0.85)' : 'rgba(147,197,253,0.85)';
    ctx.lineWidth   = 0.6;

    if (p.corners?.length === 4) {
      // corners 사용: 방위각 회전 + 중앙 offset 적용
      const cPts = p.corners.map(c => toCShifted(c.lng, c.lat));
      ctx.beginPath();
      cPts.forEach((cpt, i) => i === 0 ? ctx.moveTo(cpt.x, cpt.y) : ctx.lineTo(cpt.x, cpt.y));
      ctx.closePath();
      ctx.fill();
      ctx.stroke();

      // 패널 중앙 구분선 (셀 느낌)
      const [sw, se] = cPts;
      const nw = cPts[3], ne = cPts[2];
      const mTop = { x: (nw.x + ne.x) / 2, y: (nw.y + ne.y) / 2 };
      const mBot = { x: (sw.x + se.x) / 2, y: (sw.y + se.y) / 2 };
      ctx.strokeStyle = isShade ? 'rgba(252,165,165,0.2)' : 'rgba(147,197,253,0.2)';
      ctx.lineWidth   = 0.3;
      ctx.beginPath();
      ctx.moveTo(mTop.x, mTop.y);
      ctx.lineTo(mBot.x, mBot.y);
      ctx.stroke();
    } else {
      // corners 없을 때: fillRect + 중앙 offset 폴백
      const tl = toCShifted(p.lng,      p.lat + ph);
      const br = toCShifted(p.lng + pw, p.lat);
      ctx.fillRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);
      ctx.strokeRect(tl.x, tl.y, br.x - tl.x, br.y - tl.y);
    }

    drawnCount++;
  });

  ctx.restore();

  // ── 지붕 외곽선 (z-order: 패널 위) ──────────────────────────────────────
  ctx.beginPath();
  roofPts.forEach((pt, i) => i === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y));
  ctx.closePath();
  ctx.strokeStyle = '#FBBF24'; // amber-400
  ctx.lineWidth   = 2;
  ctx.stroke();

  roofPts.forEach(pt => {
    ctx.beginPath();
    ctx.arc(pt.x, pt.y, 3.5, 0, Math.PI * 2);
    ctx.fillStyle = '#FBBF24';
    ctx.fill();
  });

  // ── 방위 레이블 ──────────────────────────────────────────────────────────
  ctx.font      = 'bold 11px "Noto Sans KR", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = 'rgba(255,255,255,0.45)';
  ctx.fillText('↑ 북', CW / 2, 20);
  ctx.fillText('↓ 남', CW / 2, CH - 8);

  // ── 나침반 ───────────────────────────────────────────────────────────────
  const ncx = CW - 30, ncy = 30, nr = 14;
  ctx.fillStyle = 'rgba(0,0,0,0.55)';
  ctx.beginPath(); ctx.arc(ncx, ncy, nr, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.18)'; ctx.lineWidth = 1; ctx.stroke();
  // 북 (파랑)
  ctx.fillStyle = '#60a5fa';
  ctx.beginPath();
  ctx.moveTo(ncx, ncy - nr + 2); ctx.lineTo(ncx + 3.5, ncy + 1);
  ctx.lineTo(ncx, ncy - 1);      ctx.lineTo(ncx - 3.5, ncy + 1);
  ctx.closePath(); ctx.fill();
  // 남 (회색)
  ctx.fillStyle = '#4b5563';
  ctx.beginPath();
  ctx.moveTo(ncx, ncy + nr - 2); ctx.lineTo(ncx + 3.5, ncy - 1);
  ctx.lineTo(ncx, ncy + 1);      ctx.lineTo(ncx - 3.5, ncy - 1);
  ctx.closePath(); ctx.fill();
  ctx.fillStyle = '#93c5fd';
  ctx.font      = 'bold 7px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('N', ncx, ncy - nr - 3);

  // 방위각 화살표
  const az    = stats?.azimuth_deg ?? 180;
  const azRad = az * Math.PI / 180;
  ctx.strokeStyle = '#f87171';
  ctx.lineWidth   = 1.8;
  ctx.setLineDash([3, 2]);
  ctx.beginPath();
  ctx.moveTo(ncx, ncy);
  ctx.lineTo(ncx + 20 * Math.sin(azRad), ncy - 20 * Math.cos(azRad));
  ctx.stroke();
  ctx.setLineDash([]);

  // ── 스케일바 ─────────────────────────────────────────────────────────────
  // 실제 스케일: mPerDegLng × scale px/m
  const mPerDegLng   = M_PER_DEG_LAT * Math.cos(((bbox.minLat + bbox.maxLat) / 2) * Math.PI / 180);
  const contentWm    = Math.max((bbox.maxLng - bbox.minLng) * mPerDegLng, 1e-3);
  const contentHm    = Math.max((bbox.maxLat - bbox.minLat) * M_PER_DEG_LAT, 1e-3);
  const scale        = Math.min((CW - PAD * 2) / contentWm, (CH - PAD * 2) / contentHm) * 0.83;
  const scaleM       = 5;
  const scalePx      = scaleM * scale;
  const sbX = PAD + 4, sbY = CH - 14;
  ctx.strokeStyle = 'rgba(255,255,255,0.65)';
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  ctx.moveTo(sbX, sbY);               ctx.lineTo(sbX + scalePx, sbY);
  ctx.moveTo(sbX, sbY - 4);           ctx.lineTo(sbX, sbY + 4);
  ctx.moveTo(sbX + scalePx, sbY - 4); ctx.lineTo(sbX + scalePx, sbY + 4);
  ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,0.65)';
  ctx.font      = '10px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(`${scaleM}m`, sbX + scalePx / 2, sbY - 6);

  // ── 통계 오버레이 (우하단) ───────────────────────────────────────────────
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
  ctx.textAlign = 'center';
  ctx.fillStyle = 'white';
  ctx.font      = 'bold 17px sans-serif';
  ctx.fillText(`${drawnCount}매`, oX - oW / 2, oY - oH + 26);
  ctx.fillStyle = '#93c5fd';
  ctx.font      = '12px sans-serif';
  ctx.fillText(`${totalKw} kW`, oX - oW / 2, oY - oH + 46);

  console.log('[PanelLayoutCanvas] 그려진 패널:', drawnCount, '/', totalKw, 'kW');
  onPanelCountChange?.(drawnCount, parseFloat(totalKw));
  return drawnCount;
}

// ── React 컴포넌트 ───────────────────────────────────────────────────────────

export default function PanelLayoutCanvas({ layout, onPanelCountChange = null }) {
  const canvasRef = useRef(null);
  const [drawn, setDrawn] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !layout?.panels?.length) return;
    const count = draw(canvas, layout, onPanelCountChange);
    setDrawn(count ?? 0);
  }, [layout, onPanelCountChange]);

  if (!layout?.panels?.length) return null;
  const { stats } = layout;

  return (
    <div className="chart-wrapper">
      {/* 범례 + 통계 */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 10,
      }}>
        <div style={{ display: 'flex', gap: 14 }}>
          {[
            { fill: 'rgba(59,130,246,0.85)', stroke: '#93c5fd', label: `설치 패널 (${drawn}매)` },
            { fill: 'rgba(239,68,68,0.80)',  stroke: '#fca5a5', label: `음영 구역` },
            { fill: 'transparent',           stroke: '#FBBF24', label: '지붕 외곽선' },
          ].map(({ fill, stroke, label }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 20, height: 11, borderRadius: 2,
                background: fill, border: `2px solid ${stroke}`,
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
        💛 노란 외곽선 = 지붕 폴리곤 (방위각 {stats?.azimuth_deg ?? 180}° 회전 적용)
        · Turf.js PiP 필터로 외곽선 내부 패널만 표시
        · 실제 배치 {drawn}매 × 0.64kW = {(drawn * 0.64).toFixed(1)} kW
      </div>
    </div>
  );
}

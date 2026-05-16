/**
 * 태양 위치 및 패널 음영 계산 유틸리티.
 *
 * 좌표계:
 *   - 방위각(azimuth): 0°=북, 90°=동, 180°=남, 270°=서
 *   - 고도각(elevation): 0°=지평, 90°=천정
 */

const DEG = Math.PI / 180;

// 월별 태양 적위 근사값 (1~12월, 도)
export const MONTHLY_DECLINATIONS = [
  -23.1, -17.3, -8.4, 2.2, 11.9, 20.0,
   23.4,  20.4, 12.1, 1.8, -8.8, -18.8,
];

export const MONTH_LABELS = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
export const SIM_MONTHS   = [0, 3, 6, 9]; // Jan, Apr, Jul, Oct (0-indexed)

/**
 * 특정 위도·월·시간(태양시)에서 태양 고도각·방위각 계산.
 * @param {number} latDeg  위도 (°N)
 * @param {number} monthIdx 0~11
 * @param {number} hourFromNoon  태양 정오 기준 시간 (-4~+4)
 * @returns {{ elevation: number, azimuth: number }} 도 단위
 */
export function getSolarPosition(latDeg, monthIdx, hourFromNoon) {
  const dec = MONTHLY_DECLINATIONS[monthIdx] * DEG;
  const lat = latDeg * DEG;
  const ha  = hourFromNoon * 15 * DEG;   // 시각도 (15°/h)

  const sinEl = Math.sin(lat) * Math.sin(dec) + Math.cos(lat) * Math.cos(dec) * Math.cos(ha);
  const el    = Math.asin(Math.max(-1, Math.min(1, sinEl)));

  // 방위각 (0=남, 양수=서) → 북 기준으로 변환
  const cosAz = (Math.sin(dec) - Math.sin(el) * Math.sin(lat)) / (Math.cos(el) * Math.cos(lat));
  let azFromSouth = Math.acos(Math.max(-1, Math.min(1, cosAz)));
  if (ha > 0) azFromSouth = 2 * Math.PI - azFromSouth;  // 오후는 서쪽
  const azFromNorth = (azFromSouth + Math.PI) % (2 * Math.PI); // 북 기준 방위각

  return {
    elevation: el / DEG,
    azimuth:   azFromNorth / DEG,
  };
}

/**
 * 패널 격자에서 월별 음영률 계산.
 * 각 패널(row, col)에 대해 하루 동안 몇 % 시간이 음영 상태인지 반환.
 *
 * @param {Array}  panels       panel_layout.panels
 * @param {Object} stats        panel_layout.stats
 * @param {number} latDeg       위도
 * @param {number} monthIdx     0~11
 * @returns {Object}  { "row-col": shadeFraction (0~1) }
 */
export function calcShadeMatrix(panels, stats, latDeg, monthIdx) {
  const HOURS = [-4, -3.5, -3, -2.5, -2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4];
  const tiltRad      = stats.tilt_deg * DEG;
  const PANEL_H      = stats.panel_h_m  || 2.094;
  const PANEL_W      = stats.panel_w_m  || 1.134;
  const rowSpacingM  = stats.row_spacing_m;
  const colSpacingM  = stats.col_spacing_m;

  // 패널 상단 에지 높이 (경사로 인한 투영 높이)
  const hProj = PANEL_H * Math.sin(tiltRad);

  const result = {};

  for (const panel of panels) {
    const key = `${panel.row}-${panel.col}`;
    if (panel.row === 0) { result[key] = 0; continue; }  // 최남단 → 음영 없음

    let shadedCount = 0, dayCount = 0;

    for (const h of HOURS) {
      const { elevation, azimuth } = getSolarPosition(latDeg, monthIdx, h);
      if (elevation <= 2) continue;  // 지평 이하 or 저고도 제외
      dayCount++;

      const shadowLen = hProj / Math.tan(elevation * DEG);

      // 그림자의 NS 방향 성분: 북쪽(+) 방향
      // azimuth: 0=북, 180=남 → 태양이 남쪽일 때 그림자는 북쪽
      const azRad = azimuth * DEG;
      // 그림자 방향 = 태양 방위 + 180°
      const shadowNorth = shadowLen * Math.cos(azRad);  // 양수 = 북쪽
      const shadowEast  = shadowLen * Math.sin(azRad);  // 양수 = 동쪽 방향

      // 행간 음영: 남쪽 인접 행(row-1)의 패널 그림자가 현재 패널에 닿는지
      // row 1행이 row 0행에 의해 음영되는 거리 = rowSpacingM
      // 그림자가 rowSpacingM 이상이면 음영
      const rowsShaded = shadowNorth / rowSpacingM;
      if (rowsShaded >= panel.row) {
        shadedCount++;
      }
    }

    result[key] = dayCount > 0 ? shadedCount / dayCount : 0;
  }

  return result;
}

/**
 * 음영률(0~1)을 색상으로 변환.
 * 0%(초록) → 50%(노랑) → 100%(빨강) 그라데이션
 */
export function shadeToColor(fraction) {
  const f = Math.max(0, Math.min(1, fraction));
  if (f < 0.5) {
    // 초록 → 노랑
    const t = f * 2;
    const r = Math.round(22  + (255 - 22)  * t);
    const g = Math.round(163 + (193 - 163) * t);
    const b = Math.round(74  + (7   - 74)  * t);
    return `rgb(${r},${g},${b})`;
  } else {
    // 노랑 → 빨강
    const t = (f - 0.5) * 2;
    const r = Math.round(255 + (220 - 255) * t);
    const g = Math.round(193 + (38  - 193) * t);
    const b = Math.round(7   + (38  - 7)   * t);
    return `rgb(${r},${g},${b})`;
  }
}

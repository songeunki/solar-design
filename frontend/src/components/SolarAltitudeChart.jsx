/**
 * SolarAltitudeChart
 * props:
 *   data - Array(12) of { month, solar_altitude }
 *          solar_altitude: 월별 최대 태양 고도각 (°)
 */

const MONTHS = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];

// 계절별 배경 밴드 (month index, 0-based)
const SEASON_BANDS = [
  { start: 0,  end: 2,  color: 'rgba(147,197,253,0.22)', label: '겨울' },
  { start: 2,  end: 5,  color: 'rgba(134,239,172,0.22)', label: '봄'   },
  { start: 5,  end: 8,  color: 'rgba(253,186,116,0.22)', label: '여름' },
  { start: 8,  end: 11, color: 'rgba(252,211,77,0.22)',  label: '가을' },
  { start: 11, end: 12, color: 'rgba(147,197,253,0.22)', label: '겨울' },
];

const SEASON_LEGEND = [
  { label: '봄',   color: 'rgba(134,239,172,0.7)' },
  { label: '여름', color: 'rgba(253,186,116,0.7)' },
  { label: '가을', color: 'rgba(252,211,77,0.7)'  },
  { label: '겨울', color: 'rgba(147,197,253,0.7)' },
];

export default function SolarAltitudeChart({ data = [] }) {
  if (!data || data.length === 0) return null;

  const W = 620, H = 220;
  const PAD = { top: 28, right: 20, bottom: 36, left: 48 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;
  const maxAlt = 90;
  const slot = chartW / 12;

  const pts = data.map((d, i) => ({
    x:   PAD.left + i * slot + slot / 2,
    y:   PAD.top + chartH - ((d.solar_altitude || 0) / maxAlt) * chartH,
    alt: d.solar_altitude || 0,
  }));

  const polyline = pts.map(p => `${p.x},${p.y}`).join(' ');
  const yTicks = [0, 30, 60, 90];

  return (
    <div className="chart-wrapper">
      {/* 범례 */}
      <div className="chart-legend" style={{ justifyContent: 'space-between' }}>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--blue)', borderRadius: '50%' }} />
          월별 최대 태양 고도각 (°)
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {SEASON_LEGEND.map(({ label, color }) => (
            <div key={label} className="legend-item" style={{ fontSize: 11 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        aria-label="월별 태양 고도각 차트"
      >
        {/* 계절 배경 밴드 */}
        {SEASON_BANDS.map((s, i) => (
          <rect
            key={i}
            x={PAD.left + s.start * slot}
            y={PAD.top}
            width={(s.end - s.start) * slot}
            height={chartH}
            fill={s.color}
            rx="4"
          />
        ))}

        {/* Y축 그리드 */}
        {yTicks.map((v) => {
          const y = PAD.top + chartH - (v / maxAlt) * chartH;
          return (
            <g key={v}>
              <line x1={PAD.left} y1={y} x2={PAD.left + chartW} y2={y}
                stroke="#e2e8f0" strokeWidth="1" />
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize="11" fill="#a0aec0">
                {v}°
              </text>
            </g>
          );
        })}

        {/* 꺾은선 */}
        <polyline
          points={polyline}
          fill="none"
          stroke="var(--blue)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* 포인트 + 값 레이블 */}
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="4" fill="white" stroke="var(--blue)" strokeWidth="2.5" />
            <text
              x={p.x} y={p.y - 8}
              textAnchor="middle" fontSize="9.5" fill="var(--blue)" fontWeight="600"
            >
              {p.alt}°
            </text>
          </g>
        ))}

        {/* X축 레이블 */}
        {MONTHS.map((m, i) => (
          <text
            key={i}
            x={PAD.left + i * slot + slot / 2}
            y={H - 8}
            textAnchor="middle" fontSize="11" fill="#718096"
          >
            {m}
          </text>
        ))}

        {/* X축 선 */}
        <line
          x1={PAD.left} y1={PAD.top + chartH}
          x2={PAD.left + chartW} y2={PAD.top + chartH}
          stroke="#e2e8f0" strokeWidth="1.5"
        />
      </svg>
    </div>
  );
}

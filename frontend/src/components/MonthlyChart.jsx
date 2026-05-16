/**
 * MonthlyChart
 * props:
 *   data - Array(12) of { month, kwh, irradiation }
 *          irradiation: 일사량 (kWh/m²)
 *          kwh: 발전량 (kWh)
 */

const MONTHS = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];

export default function MonthlyChart({ data = [] }) {
  if (!data || data.length === 0) return null;

  const W = 620, H = 240;
  const PAD = { top: 20, right: 20, bottom: 36, left: 56 };
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top - PAD.bottom;

  const maxKwh = Math.max(...data.map((d) => d.kwh || 0), 1);
  const maxIrr = Math.max(...data.map((d) => d.irradiation || 0), 1);

  const barW = (chartW / 12) * 0.55;
  const barGap = chartW / 12;

  // 꺾은선 포인트
  const linePoints = data.map((d, i) => {
    const x = PAD.left + i * barGap + barGap / 2;
    const y = PAD.top + chartH - (d.irradiation / maxIrr) * chartH;
    return `${x},${y}`;
  });
  const polyline = linePoints.join(' ');

  // y축 눈금
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((r) => ({
    val: Math.round(maxKwh * r),
    y: PAD.top + chartH - r * chartH,
  }));

  return (
    <div className="chart-wrapper">
      {/* 범례 */}
      <div className="chart-legend">
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--orange)' }} />
          월별 발전량 (kWh)
        </div>
        <div className="legend-item">
          <div className="legend-dot" style={{ background: 'var(--blue)', borderRadius: '50%' }} />
          일사량 (kWh/m²)
        </div>
      </div>

      {/* SVG */}
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        aria-label="월별 발전량 차트"
      >
        {/* 그리드 */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={PAD.left} y1={t.y} x2={PAD.left + chartW} y2={t.y}
              stroke="#e2e8f0" strokeWidth="1"
            />
            <text
              x={PAD.left - 8} y={t.y + 4}
              textAnchor="end" fontSize="11" fill="#a0aec0"
            >
              {t.val.toLocaleString()}
            </text>
          </g>
        ))}

        {/* 막대 (발전량 - 오렌지) */}
        {data.map((d, i) => {
          const bH = ((d.kwh || 0) / maxKwh) * chartH;
          const x = PAD.left + i * barGap + (barGap - barW) / 2;
          const y = PAD.top + chartH - bH;
          return (
            <g key={i}>
              <rect
                x={x} y={y} width={barW} height={bH}
                fill="var(--orange)" rx="3" opacity="0.9"
              />
              {d.kwh > 0 && (
                <text
                  x={x + barW / 2} y={y - 4}
                  textAnchor="middle" fontSize="10" fill="var(--orange)"
                  fontWeight="600"
                >
                  {d.kwh.toLocaleString()}
                </text>
              )}
            </g>
          );
        })}

        {/* 꺾은선 (일사량 - 파랑) */}
        <polyline
          points={polyline}
          fill="none"
          stroke="var(--blue)"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {data.map((d, i) => {
          const x = PAD.left + i * barGap + barGap / 2;
          const y = PAD.top + chartH - (d.irradiation / maxIrr) * chartH;
          return (
            <circle
              key={i} cx={x} cy={y} r="4"
              fill="white" stroke="var(--blue)" strokeWidth="2.5"
            />
          );
        })}

        {/* x축 레이블 */}
        {MONTHS.map((m, i) => (
          <text
            key={i}
            x={PAD.left + i * barGap + barGap / 2}
            y={H - 8}
            textAnchor="middle" fontSize="11" fill="#718096"
          >
            {m}
          </text>
        ))}

        {/* x축 선 */}
        <line
          x1={PAD.left} y1={PAD.top + chartH}
          x2={PAD.left + chartW} y2={PAD.top + chartH}
          stroke="#e2e8f0" strokeWidth="1.5"
        />
      </svg>
    </div>
  );
}

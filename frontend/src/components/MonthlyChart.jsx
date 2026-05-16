const MONTHS = ['1','2','3','4','5','6','7','8','9','10','11','12']

export default function MonthlyChart({ values }) {
  if (!values || values.length !== 12) return null

  const W = 640, H = 210
  const pl = 48, pr = 16, pt = 24, pb = 40
  const cw = W - pl - pr
  const ch = H - pt - pb

  const maxV    = Math.max(...values) || 1
  const barSlot = cw / 12
  const bw      = barSlot * 0.58
  const gap     = (barSlot - bw) / 2

  const gridLines = [0.25, 0.5, 0.75, 1.0]

  // Blue line: connect bar center tops
  const linePoints = values.map((v, i) => {
    const cx = pl + i * barSlot + barSlot / 2
    const y  = pt + ch - (v / maxV) * ch
    return `${cx.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  return (
    <div className="chart-card">
      <div className="chart-header">
        <span className="chart-title">월별 예상 발전량 (kWh)</span>
        <div className="chart-legend">
          <span className="legend-item">
            <span className="legend-bar" />발전량
          </span>
          <span className="legend-item">
            <span className="legend-line" />추세선
          </span>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        <defs>
          <linearGradient id="barOrange" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#FF8050" />
            <stop offset="100%" stopColor="#E85520" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {gridLines.map(pct => {
          const y = pt + ch * (1 - pct)
          return (
            <g key={pct}>
              <line
                x1={pl} y1={y} x2={W - pr} y2={y}
                stroke="rgba(0,0,0,0.06)" strokeWidth="1"
                strokeDasharray={pct < 1 ? '4 3' : 'none'}
              />
              <text
                x={pl - 6} y={y + 4} textAnchor="end"
                fontSize="9.5" fill="#9AA5B4"
                fontFamily="'Noto Sans KR', sans-serif"
              >
                {Math.round(maxV * pct)}
              </text>
            </g>
          )
        })}

        {/* Orange bars */}
        {values.map((v, i) => {
          const bh = (v / maxV) * ch
          const x  = pl + i * barSlot + gap
          const y  = pt + ch - bh
          const cx = pl + i * barSlot + barSlot / 2
          return (
            <g key={i}>
              <rect
                x={x} y={y} width={bw} height={bh}
                fill="url(#barOrange)" rx="3" ry="3" opacity="0.88"
              />
              <text
                x={cx} y={H - 10} textAnchor="middle"
                fontSize="9.5" fill="#9AA5B4"
                fontFamily="'Noto Sans KR', sans-serif"
              >
                {MONTHS[i]}
              </text>
            </g>
          )
        })}

        {/* Blue trend line */}
        <polyline
          points={linePoints}
          fill="none"
          stroke="#1E6FD9"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
        />

        {/* Dots on line */}
        {values.map((v, i) => {
          const cx = pl + i * barSlot + barSlot / 2
          const y  = pt + ch - (v / maxV) * ch
          return (
            <circle
              key={i}
              cx={cx.toFixed(1)} cy={y.toFixed(1)} r="3.8"
              fill="#fff" stroke="#1E6FD9" strokeWidth="2.2"
            />
          )
        })}

        {/* Y axis line */}
        <line
          x1={pl} y1={pt} x2={pl} y2={pt + ch}
          stroke="rgba(0,0,0,0.08)" strokeWidth="1"
        />
      </svg>
    </div>
  )
}

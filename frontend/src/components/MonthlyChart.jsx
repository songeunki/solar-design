const MONTHS = ['1','2','3','4','5','6','7','8','9','10','11','12']

export default function MonthlyChart({ values }) {
  if (!values || values.length !== 12) return null

  const W = 640, H = 200
  const pl = 48, pr = 12, pt = 20, pb = 38
  const cw = W - pl - pr
  const ch = H - pt - pb

  const maxV    = Math.max(...values) || 1
  const barSlot = cw / 12
  const bw      = barSlot * 0.62
  const gap     = (barSlot - bw) / 2

  const gridLines = [0.25, 0.5, 0.75, 1.0]
  const maxIdx    = values.indexOf(Math.max(...values))
  const minIdx    = values.indexOf(Math.min(...values))

  return (
    <div className="chart-card">
      <p className="chart-title">월별 발전량 (kWh)</p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
      >
        <defs>
          <linearGradient id="barBase" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2563EB" />
            <stop offset="100%" stopColor="#1E40AF" />
          </linearGradient>
          <linearGradient id="barPeak" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#60A5FA" />
            <stop offset="100%" stopColor="#3B82F6" />
          </linearGradient>
          <linearGradient id="barLow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1D4ED8" />
            <stop offset="100%" stopColor="#1E3A8A" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {gridLines.map(pct => {
          const y = pt + ch * (1 - pct)
          return (
            <g key={pct}>
              <line
                x1={pl} y1={y} x2={W - pr} y2={y}
                stroke="rgba(0,0,0,0.07)" strokeWidth="1"
                strokeDasharray={pct === 1 ? 'none' : '4 3'}
              />
              <text
                x={pl - 6} y={y + 4}
                textAnchor="end" fontSize="9.5" fill="#94a3b8"
                fontFamily="'Outfit', sans-serif"
              >
                {Math.round(maxV * pct)}
              </text>
            </g>
          )
        })}

        {/* Bars */}
        {values.map((v, i) => {
          const bh   = (v / maxV) * ch
          const x    = pl + i * barSlot + gap
          const y    = pt + ch - bh
          const cx   = pl + i * barSlot + barSlot / 2
          const fill = i === maxIdx ? 'url(#barPeak)' : i === minIdx ? 'url(#barLow)' : 'url(#barBase)'

          return (
            <g key={i}>
              <rect x={x} y={y} width={bw} height={bh} fill={fill} rx="3" ry="3" />
              {bh > 24 && (
                <text
                  x={cx} y={y + 13}
                  textAnchor="middle" fontSize="9" fill="rgba(255,255,255,0.9)"
                  fontWeight="600" fontFamily="'Outfit', sans-serif"
                >
                  {Math.round(v)}
                </text>
              )}
              <text
                x={cx} y={H - 7}
                textAnchor="middle" fontSize="9.5" fill="#94a3b8"
              >
                {MONTHS[i]}
              </text>
            </g>
          )
        })}

        {/* Y axis */}
        <line
          x1={pl} y1={pt} x2={pl} y2={pt + ch}
          stroke="rgba(0,0,0,0.07)" strokeWidth="1"
        />
      </svg>
    </div>
  )
}

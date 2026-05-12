const MONTHS = ['1','2','3','4','5','6','7','8','9','10','11','12']

export default function MonthlyChart({ values }) {
  if (!values || values.length !== 12) return null

  const W = 640, H = 200
  const pl = 50, pr = 12, pt = 20, pb = 36
  const cw = W - pl - pr
  const ch = H - pt - pb

  const maxV = Math.max(...values) || 1
  const barSlot = cw / 12
  const bw = barSlot * 0.65
  const gap = (barSlot - bw) / 2

  const gridPcts = [0.25, 0.5, 0.75, 1.0]

  return (
    <div className="chart-card card">
      <p className="chart-title">📊 월별 발전량 (kWh)</p>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        style={{ width: '100%', height: 'auto', display: 'block' }}
      >
        <defs>
          <linearGradient id="barGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#f59e0b" />
            <stop offset="100%" stopColor="#f97316" />
          </linearGradient>
          <linearGradient id="barGradMax" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fbbf24" />
            <stop offset="100%" stopColor="#f59e0b" />
          </linearGradient>
          <linearGradient id="barGradMin" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#fed7aa" />
            <stop offset="100%" stopColor="#fdba74" />
          </linearGradient>
        </defs>

        {/* grid lines */}
        {gridPcts.map(pct => {
          const y = pt + ch * (1 - pct)
          return (
            <g key={pct}>
              <line x1={pl} y1={y} x2={W - pr} y2={y} stroke="#f3f4f6" strokeWidth="1.5" />
              <text x={pl - 6} y={y + 4} textAnchor="end" fontSize="10" fill="#9ca3af">
                {Math.round(maxV * pct)}
              </text>
            </g>
          )
        })}

        {/* bars */}
        {values.map((v, i) => {
          const bh = (v / maxV) * ch
          const x = pl + i * barSlot + gap
          const y = pt + ch - bh
          const cx = pl + i * barSlot + barSlot / 2
          const isMax = v === Math.max(...values)
          const isMin = v === Math.min(...values)
          const fill = isMax ? 'url(#barGradMax)' : isMin ? 'url(#barGradMin)' : 'url(#barGrad)'

          return (
            <g key={i}>
              <rect x={x} y={y} width={bw} height={bh} fill={fill} rx="3" />
              {bh > 22 && (
                <text x={cx} y={y + 14} textAnchor="middle" fontSize="9.5" fill="#fff" fontWeight="600">
                  {Math.round(v)}
                </text>
              )}
              <text x={cx} y={H - 6} textAnchor="middle" fontSize="10" fill="#6b7280">
                {MONTHS[i]}월
              </text>
            </g>
          )
        })}

        {/* Y-axis */}
        <line x1={pl} y1={pt} x2={pl} y2={pt + ch} stroke="#e5e7eb" strokeWidth="1" />
      </svg>
    </div>
  )
}

const STEPS = ['주소 조회', '건물 정보', '기상 데이터', '설계 분석', '보고서 생성']

export default function ProgressBar({ step, total, message }) {
  const pct = total > 0 ? Math.round((step / total) * 100) : 0

  return (
    <div className="progress-wrap">
      <div className="progress-header">
        <span className="progress-label">
          <span className="status-dot running" style={{ marginRight: 8 }} />
          {message || '분석 중…'}
        </span>
        <span className="progress-pct">{pct}%</span>
      </div>

      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>

      <div className="progress-steps">
        {STEPS.map((label, i) => {
          const idx = i + 1
          const isDone   = idx < step
          const isActive = idx === step
          return (
            <div
              key={label}
              className={`progress-step-item ${isDone ? 'done' : isActive ? 'active' : ''}`}
            >
              <span className="step-dot" />
              {isDone ? '✓ ' : ''}{label}
            </div>
          )
        })}
      </div>
    </div>
  )
}

/**
 * ProgressBar
 * props:
 *   step    - 현재 완료 단계 (0~5, 5=완료)
 *   message - 현재 진행 상태 메시지
 */

const STEPS = [
  { label: '주소 변환', icon: '📍' },
  { label: '건물 정보', icon: '🏢' },
  { label: '일사량 수집', icon: '🌤️' },
  { label: '지붕 분석',  icon: '📐' },
  { label: '설계 완료',  icon: '✅' },
];

export default function ProgressBar({ step = 0, message = '분석을 시작합니다...' }) {
  const pct = Math.round((step / STEPS.length) * 100);

  return (
    <div className="progress-wrapper">
      {/* 단계 표시 */}
      <div className="progress-steps">
        {STEPS.map((s, i) => {
          const status =
            i < step ? 'done' : i === step ? 'active' : 'pending';
          return (
            <div key={i} className={`progress-step ${status}`}>
              <div className="progress-step-circle">
                {status === 'done' ? '✓' : status === 'active' ? s.icon : i + 1}
              </div>
              <div className="progress-step-label">{s.label}</div>
            </div>
          );
        })}
      </div>

      {/* 바 */}
      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>

      {/* 상태 텍스트 */}
      <div className="progress-status-text">
        {step < STEPS.length && <span className="spinner" />}
        <span>{message}</span>
        <span
          style={{ marginLeft: 'auto', fontWeight: 700, color: 'var(--blue)' }}
        >
          {pct}%
        </span>
      </div>
    </div>
  );
}

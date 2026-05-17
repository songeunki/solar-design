/**
 * ProgressBar
 * props:
 *   step    - 현재 완료 단계 (0~5, 5=완료)
 *   message - 현재 진행 상태 메시지
 */

const STEPS = [
  { icon: 'fa-solid fa-location-dot', label: '주소 조회' },
  { icon: 'fa-solid fa-building',     label: '건물 정보' },
  { icon: 'fa-solid fa-cloud-sun',    label: '기상 데이터' },
  { icon: 'fa-solid fa-solar-panel',  label: '설계 분석' },
  { icon: 'fa-solid fa-chart-line',   label: '완료' },
];

export default function ProgressBar({ step = 0, message = '분석을 시작합니다...' }) {
  const pct = Math.round((step / STEPS.length) * 100);

  const getStepState = (i) =>
    i < step ? 'done' : i === step ? 'active' : 'pending';

  return (
    <div className="progress-card">
      {/* 단계 아이콘 */}
      <div className="progress-steps">
        {STEPS.map((s, i) => {
          const state = getStepState(i);
          return (
            <div key={i} className={`progress-step ${state}`}>
              <div className="step-icon-wrap">
                {state === 'done'
                  ? <i className="fa-solid fa-check"></i>
                  : state === 'active'
                  ? <i className={`${s.icon} fa-beat`}></i>
                  : <i className={s.icon}></i>
                }
              </div>
              <span className="step-label">{s.label}</span>
            </div>
          );
        })}
      </div>

      {/* 진행 바 */}
      <div className="progress-bar-track">
        <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
      </div>

      {/* 상태 텍스트 */}
      <div className="progress-status-text">
        {step < STEPS.length && (
          <i className="fa-solid fa-spinner"></i>
        )}
        <span>{message}</span>
        <span style={{ marginLeft: 'auto', fontWeight: 700 }}>{pct}%</span>
      </div>
    </div>
  );
}

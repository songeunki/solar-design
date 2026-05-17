# Task 6: 분석 중 프로그레스바 아이콘 현대화

## 현재 문제
ProgressBar.jsx의 단계 아이콘이 올드한 숫자 원형 스타일

## 변경 방향
Font Awesome 6 아이콘 + 다크 테마에 맞는 현대적 스타일

### ProgressBar.jsx 수정
각 단계별 FA 아이콘으로 교체:

```jsx
const STEPS = [
  { icon: 'fa-solid fa-location-dot',   label: '주소 조회' },
  { icon: 'fa-solid fa-building',        label: '건물 정보' },
  { icon: 'fa-solid fa-cloud-sun',       label: '기상 데이터' },
  { icon: 'fa-solid fa-solar-panel',     label: '설계 분석' },
  { icon: 'fa-solid fa-chart-line',      label: '완료' },
]

// 렌더링
<div className="progress-steps">
  {STEPS.map((step, i) => (
    <div key={i} className={`progress-step ${getStepState(i)}`}>
      <div className="step-icon-wrap">
        {getStepState(i) === 'done'
          ? <i className="fa-solid fa-check"></i>
          : getStepState(i) === 'active'
          ? <i className={`${step.icon} fa-beat`}></i>
          : <i className={step.icon}></i>
        }
      </div>
      <span className="step-label">{step.label}</span>
    </div>
  ))}
</div>
```

### CSS (index.css에 추가)
```css
.progress-steps {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  position: relative;
}

/* 연결선 */
.progress-steps::before {
  content: '';
  position: absolute;
  top: 20px;
  left: 10%;
  right: 10%;
  height: 2px;
  background: var(--border-color, #2A3F5F);
  z-index: 0;
}

.progress-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  z-index: 1;
}

.step-icon-wrap {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  border: 2px solid var(--border-color, #2A3F5F);
  background: var(--bg-card, #1A2535);
  color: var(--text-secondary, #8899AA);
  transition: all 0.3s ease;
}

/* 완료 단계 */
.progress-step.done .step-icon-wrap {
  background: #00E676;
  border-color: #00E676;
  color: #000;
  box-shadow: 0 0 12px rgba(0, 230, 118, 0.4);
}

/* 진행 중 단계 */
.progress-step.active .step-icon-wrap {
  background: var(--accent-blue, #00B4D8);
  border-color: var(--accent-blue, #00B4D8);
  color: #fff;
  box-shadow: 0 0 16px rgba(0, 180, 216, 0.5);
  animation: pulse-glow 1.5s ease-in-out infinite;
}

/* 미완료 단계 */
.progress-step.pending .step-icon-wrap {
  opacity: 0.4;
}

.step-label {
  font-size: 11px;
  color: var(--text-secondary, #8899AA);
  white-space: nowrap;
}

.progress-step.done .step-label,
.progress-step.active .step-label {
  color: var(--text-primary, #fff);
  font-weight: 600;
}

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 16px rgba(0, 180, 216, 0.5); }
  50% { box-shadow: 0 0 24px rgba(0, 180, 216, 0.9); }
}

/* 프로그레스 바 */
.progress-bar-track {
  height: 6px;
  background: var(--border-color, #2A3F5F);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 12px;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #00B4D8, #00E676);
  border-radius: 3px;
  transition: width 0.5s ease;
  box-shadow: 0 0 8px rgba(0, 180, 216, 0.5);
}

/* 현재 단계 텍스트 */
.progress-status-text {
  font-size: 13px;
  color: var(--accent-blue, #00B4D8);
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-status-text .fa-spinner {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

### 프로그레스 카드 전체 스타일도 개선
```css
.progress-card {
  background: var(--bg-card, #1A2535);
  border: 1px solid var(--border-color, #2A3F5F);
  border-radius: 16px;
  padding: 28px 32px;
  max-width: 480px;
  width: 90%;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}
```

git add -A && git commit -m "feat: 프로그레스바 아이콘 현대화 (FA6 + 글로우 애니메이션)" && git push origin master

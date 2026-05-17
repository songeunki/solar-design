# Task 4: 대시보드 레이아웃 전면 개편

## 방향
- 에너지/태양광 전문 대시보드 스타일
- 입력은 모달/팝업, 결과가 전체화면 집중
- 참고 스타일: 태양광 모니터링 시스템 (SCADA/EMS 느낌)
- 색상: 딥네이비(#0A1628) 배경 + 시아노블루(#00B4D8) 포인트 + 화이트 텍스트

## 구체적 변경사항

### 1. 전체 레이아웃 (App.jsx + index.css)
기존: 좌측 입력패널 고정 + 우측 결과
변경:
- 헤더: 높이 56px, 딥네이비 배경, 좌측 로고+타이틀, 우측 "새 분석" 버튼
- 메인: 전체화면 결과 대시보드
- 분석 전: 중앙에 큰 "분석 시작" 버튼 + 최근 분석 목록
- 분석 후: 결과 대시보드 풀화면

배경색: #0F1923 (딥다크)
카드 배경: #1A2535
테두리: #2A3F5F
포인트컬러: #00B4D8 (시아노블루)
성공컬러: #00E676 (그린)
경고컬러: #FFB300 (앰버)

### 2. 입력 모달 (AddressInput → 모달로 변경)
- "새 분석 시작" 버튼 클릭 시 모달 오픈
- 모달: 중앙 팝업, 반투명 오버레이
- 모달 내부: 주소입력 + 방위각 슬라이더
- 분석 시작 버튼 → 모달 닫히고 결과 화면으로

App.jsx에서:
```jsx
const [showModal, setShowModal] = useState(false)
// 분석 시작 전: <WelcomeScreen onStart={() => setShowModal(true)} />
// 모달: <AnalysisModal show={showModal} onClose={() => setShowModal(false)} onAnalyze={handleAnalyze} />
```

### 3. 결과 대시보드 (SingleAnalysis.jsx 개편)
분석 완료 후 전체화면:

상단 KPI 바 (4개 카드 가로 배열):
```
[⚡ 28.16kW 설치용량] [☀️ 35,468kWh 연간발전] [💰 532만원 연간수익] [⏱️ 5.3년 투자회수]
```
스타일: 카드 배경 #1A2535, 상단 컬러라인, 숫자 큰 폰트(28px), 단위 작은폰트

중단 2컬럼:
- 좌(40%): 카카오맵 (위성 + 패널오버레이)
- 우(60%): 탭 결과 (입지/수익/설계/규제/AI)

탭 스타일:
- 비활성: 텍스트 #8899AA
- 활성: 텍스트 흰색 + 하단 #00B4D8 라인 3px
- 배경: 카드와 동일 #1A2535

### 4. 헤더 개편 (App.jsx)
```jsx
<header className="app-header-dark">
  <div className="header-left">
    <i className="fa-solid fa-solar-panel header-icon"></i>
    <span className="header-title">SolarDesign AI</span>
    <span className="header-badge">Beta v1.0</span>
  </div>
  <div className="header-center">
    <button className={`header-tab ${mode==='single'?'active':''}`} onClick={()=>setMode('single')}>
      <i className="fa-solid fa-house"></i> 단일 분석
    </button>
    <button className={`header-tab ${mode==='compare'?'active':''}`} onClick={()=>setMode('compare')}>
      <i className="fa-solid fa-code-compare"></i> 비교 분석
    </button>
  </div>
  <div className="header-right">
    {hasResult && (
      <button className="btn-new-analysis" onClick={resetAnalysis}>
        <i className="fa-solid fa-rotate"></i> 새 분석
      </button>
    )}
    <button className="btn-admin" onClick={()=>navigate('/admin')}>
      <i className="fa-solid fa-gear"></i>
    </button>
  </div>
</header>
```

### 5. 웰컴 스크린 (분석 전 화면)
```jsx
<div className="welcome-screen">
  <div className="welcome-hero">
    <i className="fa-solid fa-solar-panel welcome-icon"></i>
    <h1>AI 태양광 입지 분석</h1>
    <p>주소 하나로 수익성, 설계, 규제까지 자동 분석</p>
    <button className="btn-start-analysis" onClick={() => setShowModal(true)}>
      <i className="fa-solid fa-magnifying-glass"></i>
      분석 시작하기
    </button>
  </div>
</div>
```

### 6. CSS 핵심 변수 (index.css 상단에 추가/덮어쓰기)
```css
:root {
  --bg-primary: #0F1923;
  --bg-card: #1A2535;
  --bg-card-hover: #223044;
  --border-color: #2A3F5F;
  --text-primary: #FFFFFF;
  --text-secondary: #8899AA;
  --accent-blue: #00B4D8;
  --accent-green: #00E676;
  --accent-amber: #FFB300;
  --accent-red: #FF5252;
  --header-height: 56px;
}

body {
  background: var(--bg-primary);
  color: var(--text-primary);
}

.app-header-dark {
  background: #0A1628;
  border-bottom: 1px solid var(--border-color);
  height: var(--header-height);
  display: flex;
  align-items: center;
  padding: 0 24px;
  justify-content: space-between;
  position: fixed;
  top: 0; left: 0; right: 0;
  z-index: 100;
}
```

## 주의사항
- 기존 solaroncare 스타일 CSS는 삭제하지 말고 새 클래스로 오버라이드
- 카카오맵은 그대로 유지 (높이만 조정)
- 모바일 반응형은 기존 브레이크포인트 유지
- React Router는 그대로 유지 (/admin 경로 유지)

git add -A && git commit -m "feat: 다크 대시보드 레이아웃 전면 개편" && git push origin master

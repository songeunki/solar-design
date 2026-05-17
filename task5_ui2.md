# Task 5: 반응형 모바일 최적화

## 목표
모바일(~767px)과 태블릿(768~1279px)에서 다크 대시보드가 완전히 작동하도록 최적화

## 1. 헤더 모바일 최적화 (App.jsx + index.css)

모바일에서 헤더 중앙 탭이 잘리는 문제 해결:
```css
@media (max-width: 767px) {
  .app-header-dark {
    padding: 0 12px;
    flex-wrap: wrap;
    height: auto;
    min-height: 56px;
  }
  .header-center {
    order: 3;
    width: 100%;
    border-top: 1px solid var(--border-color);
    padding: 4px 0;
  }
  .header-tab {
    flex: 1;
    font-size: 12px;
    padding: 8px 4px;
  }
  .header-left .header-title {
    font-size: 14px;
  }
  .header-badge { display: none; }
}
```

## 2. 웰컴 스크린 모바일
```css
@media (max-width: 767px) {
  .welcome-screen {
    padding: 20px 16px;
  }
  .welcome-icon { font-size: 48px; }
  .welcome-hero h1 { font-size: 22px; }
  .welcome-hero p { font-size: 14px; }
  .btn-start-analysis {
    width: 100%;
    padding: 14px;
    font-size: 16px;
  }
}
```

## 3. 분석 모달 모바일
```css
@media (max-width: 767px) {
  .modal-box {
    width: 100%;
    height: 100%;
    max-width: none;
    border-radius: 0;
    margin: 0;
  }
  .modal-overlay {
    align-items: flex-end;  /* 하단 슬라이드업 방식 */
  }
  .modal-body {
    padding: 16px;
  }
}
```

## 4. KPI 카드 바 모바일
```css
@media (max-width: 767px) {
  .dashboard-kpi-bar {
    grid-template-columns: repeat(2, 1fr);  /* 2열 그리드 */
    gap: 8px;
    padding: 8px;
  }
  .dashboard-kpi-card {
    padding: 12px;
  }
  .kpi-value { font-size: 20px; }
  .kpi-label { font-size: 11px; }
}
```

## 5. 대시보드 바디 모바일 (지도 + 탭 결과)
```css
@media (max-width: 767px) {
  .dashboard-body {
    flex-direction: column;  /* 세로 스택 */
  }
  .dashboard-map {
    width: 100%;
    height: 250px;  /* 지도 높이 고정 */
    flex-shrink: 0;
  }
  .dashboard-tabs {
    width: 100%;
    height: auto;
    overflow-y: auto;
  }
}
```

## 6. 탭 버튼 모바일 스크롤
탭이 5개라 모바일에서 잘림 → 가로 스크롤:
```css
@media (max-width: 767px) {
  .result-tab-bar {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    white-space: nowrap;
    display: flex;
  }
  .result-tab-bar::-webkit-scrollbar { display: none; }
  .result-tab-btn {
    flex-shrink: 0;
    font-size: 12px;
    padding: 10px 12px;
  }
}
```

## 7. 결과 카드/테이블 모바일
```css
@media (max-width: 767px) {
  .result-section {
    padding: 12px;
  }
  .info-grid {
    grid-template-columns: 1fr;  /* 1열로 */
  }
  .compare-grid {
    grid-template-columns: 1fr;
  }
  /* 긴 텍스트 줄바꿈 */
  .info-value {
    word-break: break-all;
    text-align: right;
    font-size: 13px;
  }
}
```

## 8. 하단 다운로드 버튼 모바일
```css
@media (max-width: 767px) {
  .download-buttons {
    flex-direction: column;
    gap: 8px;
  }
  .download-buttons button,
  .download-buttons a {
    width: 100%;
  }
}
```

## 9. 태블릿 (768~1279px) 조정
```css
@media (min-width: 768px) and (max-width: 1279px) {
  .dashboard-kpi-bar {
    grid-template-columns: repeat(4, 1fr);
  }
  .dashboard-body {
    flex-direction: row;
  }
  .dashboard-map {
    width: 40%;
  }
  .dashboard-tabs {
    width: 60%;
  }
}
```

## 10. 터치 UX 개선
```css
/* 터치 타겟 최소 44px */
button, a, .result-tab-btn {
  min-height: 44px;
}
/* 탭 간격 */
@media (max-width: 767px) {
  .result-tab-btn { min-height: 44px; }
}
/* 스크롤 부드럽게 */
.dashboard-tabs {
  -webkit-overflow-scrolling: touch;
}
/* 호버 효과 모바일에서 제거 */
@media (hover: none) {
  .dashboard-kpi-card:hover { transform: none; }
  .result-tab-btn:hover { background: transparent; }
}
```

## 수정 파일
- frontend/src/index.css: 위 미디어쿼리 전부 추가/수정
- frontend/src/App.jsx: 헤더 모바일 메뉴 처리
- frontend/src/components/SingleAnalysis.jsx: 모달 모바일 처리

git add -A && git commit -m "feat: 모바일/태블릿 반응형 완전 최적화" && git push origin master

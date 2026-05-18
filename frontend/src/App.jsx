import { useState } from 'react';
import './index.css';
import './App.css';
import SingleAnalysis from './components/SingleAnalysis';
import CompareAnalysis from './components/CompareAnalysis';
import AdminPage from './components/AdminPage';

export default function App() {
  if (window.location.pathname === '/admin') {
    return <AdminPage />;
  }

  const [mode, setMode]           = useState('single');
  const [hasResult, setHasResult] = useState(false);
  const [resetKey, setResetKey]   = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const handleReset = () => {
    setHasResult(false);
    setIsLoading(false);
    setResetKey(k => k + 1);
  };

  const handleLogoClick = () => {
    if (isLoading) {
      if (!window.confirm('분석이 진행 중입니다. 메인 화면으로 이동하시겠습니까?')) return;
    }
    handleReset();
  };

  return (
    <div className="app-container">
      {/* ===== 다크 헤더 ===== */}
      <header className="app-header-dark">
        <div
          className="header-left"
          style={{ cursor: 'pointer' }}
          onClick={handleLogoClick}
          title="메인 화면으로"
        >
          <div className="header-logo-icon-dark">
            <i className="fa-solid fa-solar-panel"></i>
          </div>
          <span className="header-title">SolarDesign AI</span>
          <span className="header-badge-dark">Beta v1.0</span>
        </div>

        <div className="header-center" style={{marginTop: '8px', marginBottom: '8px'}}>
          <button
            className={`header-tab ${mode === 'single' ? 'active' : ''}`}
            onClick={() => { setMode('single'); handleReset(); }}
          >
            <i className="fa-solid fa-house"></i> 단일 분석
          </button>
          <button
            className={`header-tab ${mode === 'compare' ? 'active' : ''}`}
            onClick={() => { setMode('compare'); handleReset(); }}
          >
            <i className="fa-solid fa-code-compare"></i> 비교 분석
          </button>
        </div>

        <div className="header-right">
          {hasResult && (
            <button className="btn-new-analysis" onClick={handleReset}>
              <i className="fa-solid fa-rotate"></i> 새 분석
            </button>
          )}
          <a href="/admin" className="btn-admin" title="관리자 설정">
            <i className="fa-solid fa-gear"></i>
          </a>
        </div>
      </header>

      {/* ===== 메인 ===== */}
      <main className="app-main-dark">
        {mode === 'single'
          ? <SingleAnalysis key={resetKey} onResultChange={setHasResult} onLoadingChange={setIsLoading} />
          : <CompareAnalysis />
        }
      </main>
    </div>
  );
}

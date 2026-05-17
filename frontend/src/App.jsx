import { useState } from 'react';
import './index.css';
import './App.css';
import SingleAnalysis from './components/SingleAnalysis';
import CompareAnalysis from './components/CompareAnalysis';
import AdminPage from './components/AdminPage';

export default function App() {
  // /admin 경로면 관리자 페이지 렌더링
  if (window.location.pathname === '/admin') {
    return <AdminPage />;
  }

  const [activeTab, setActiveTab] = useState('single');

  return (
    <div className="app-container">
      {/* ===== 헤더 ===== */}
      <header className="app-header">
        <div className="header-logo">
          <div className="header-logo-icon">☀️</div>
          AI 태양광 입지 분석 자동화 프로그램
        </div>
        <span className="header-badge">Beta v1.0</span>
      </header>

      {/* ===== 메인 ===== */}
      <main className="app-main">
        {/* 탭 */}
        <div className="tab-bar" style={{ marginBottom: 20 }}>
          <button
            className={`tab-btn ${activeTab === 'single' ? 'active' : ''}`}
            onClick={() => setActiveTab('single')}
          >
            🏠 단일 분석
          </button>
          <button
            className={`tab-btn ${activeTab === 'compare' ? 'active' : ''}`}
            onClick={() => setActiveTab('compare')}
          >
            ⚖️ 비교 분석
          </button>
        </div>

        {activeTab === 'single' ? <SingleAnalysis /> : <CompareAnalysis />}
      </main>
    </div>
  );
}

import { useState } from 'react';
import './index.css';
import './App.css';
import SingleAnalysis from './components/SingleAnalysis';
import CompareAnalysis from './components/CompareAnalysis';

export default function App() {
  const [activeTab, setActiveTab] = useState('single');

  return (
    <div className="app-container">
      {/* ===== 헤더 ===== */}
      <header className="app-header">
        <div className="header-logo">
          <div className="header-logo-icon">☀️</div>
          태양광 설계 자동화
        </div>
        <span className="header-badge">Beta v1.0</span>
      </header>

      {/* ===== 메인 ===== */}
      <main className="app-main">
        {/* 탭 */}
        <div className="tab-bar">
          <button
            className={`tab-btn ${activeTab === 'single' ? 'active' : ''}`}
            onClick={() => setActiveTab('single')}
          >
            🏠 단일 건물 분석
          </button>
          <button
            className={`tab-btn ${activeTab === 'compare' ? 'active' : ''}`}
            onClick={() => setActiveTab('compare')}
          >
            ⚖️ 복수 건물 비교
          </button>
        </div>

        {activeTab === 'single' ? <SingleAnalysis /> : <CompareAnalysis />}
      </main>
    </div>
  );
}

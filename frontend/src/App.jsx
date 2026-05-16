import { useState } from 'react'
import SingleAnalysis from './components/SingleAnalysis'
import CompareAnalysis from './components/CompareAnalysis'
import './App.css'

const TABS = [
  { id: 'single',  label: '단일 분석' },
  { id: 'compare', label: '비교 분석' },
]

function SunIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <circle cx="11" cy="11" r="4.5" fill="white" />
      <path
        d="M11 2v2.5M11 17.5V20M2 11h2.5M17.5 11H20M4.6 4.6l1.8 1.8M15.6 15.6l1.8 1.8M4.6 17.4l1.8-1.8M15.6 6.4l1.8-1.8"
        stroke="white" strokeWidth="1.8" strokeLinecap="round"
      />
    </svg>
  )
}

export default function App() {
  const [tab, setTab] = useState('single')

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon"><SunIcon /></div>
            <div className="logo-text">
              <span className="logo-name">SolarDesign</span>
              <span className="logo-sub">태양광 설계 시스템</span>
            </div>
          </div>

          <nav className="header-tabs">
            {TABS.map(t => (
              <button
                key={t.id}
                className={`header-tab ${tab === t.id ? 'active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <div className="header-right">
            <div className="live-badge">
              <span className="live-dot" />
              실시간 분석
            </div>
          </div>
        </div>
      </header>

      <main className="main">
        {tab === 'single'  && <SingleAnalysis />}
        {tab === 'compare' && <CompareAnalysis />}
      </main>

      <footer className="footer">
        <span>© 2025 SolarDesign</span>
        <span className="footer-sep">·</span>
        <span>AI 기반 태양광 설계 자동화</span>
      </footer>
    </div>
  )
}

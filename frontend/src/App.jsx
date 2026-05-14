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
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="7" cy="7" r="2.8" fill="white" />
      <path
        d="M7 1.2v1.6M7 11.2v1.6M1.2 7h1.6M11.2 7h1.6M2.9 2.9l1.1 1.1M9.9 9.9l1.1 1.1M2.9 11.1l1.1-1.1M9.9 4.1l1.1-1.1"
        stroke="white" strokeWidth="1.4" strokeLinecap="round"
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
            <span className="logo-name">SolarDesign</span>
            <span className="logo-badge">PRO</span>
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
              Live
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

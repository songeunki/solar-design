import { useState } from 'react'
import SingleAnalysis from './components/SingleAnalysis'
import CompareAnalysis from './components/CompareAnalysis'
import './App.css'

const TABS = [
  { id: 'single', label: '단일 건물 분석' },
  { id: 'compare', label: '복수 건물 비교' },
]

export default function App() {
  const [tab, setTab] = useState('single')

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-mark">☀</div>
            <span className="logo-name">SolarDesign</span>
            <span className="logo-badge">BETA</span>
          </div>
        </div>
      </header>

      <main className="main">
        <nav className="tab-nav">
          {TABS.map(t => (
            <button
              key={t.id}
              className={`tab-btn ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>

        <div className="tab-content">
          {tab === 'single'  && <SingleAnalysis />}
          {tab === 'compare' && <CompareAnalysis />}
        </div>
      </main>

      <footer className="footer">SolarDesign · AI 기반 태양광 설계 자동화</footer>
    </div>
  )
}

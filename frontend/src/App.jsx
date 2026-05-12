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
            <span className="logo-icon">☀️</span>
            <span className="logo-text">태양광 설계 자동화</span>
          </div>
          <p className="logo-sub">주소 입력 → AI 분석 → 설계 보고서 자동 생성</p>
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

        {tab === 'single'  && <SingleAnalysis />}
        {tab === 'compare' && <CompareAnalysis />}
      </main>

      <footer className="footer">
        <p>© 2026 태양광 설계 자동화 · API: localhost:8001</p>
      </footer>
    </div>
  )
}

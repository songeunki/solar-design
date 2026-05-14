import { useState, useRef } from 'react'
import AddressInput from './AddressInput'
import ProgressBar from './ProgressBar'
import ResultCards from './ResultCards'

const _proto  = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_URL  = `${_proto}//${window.location.host}/ws/analyze`

function emptyEntry() {
  return { id: Date.now() + Math.random(), value: '', state: 'idle', progress: null, result: null, error: '' }
}

export default function CompareAnalysis() {
  const [entries, setEntries] = useState([emptyEntry(), emptyEntry()])
  const [activeTab, setActiveTab] = useState(0)
  const [running, setRunning] = useState(false)
  const wsRefs = useRef([])

  function updateEntry(idx, patch) {
    setEntries(prev => prev.map((e, i) => i === idx ? { ...e, ...patch } : e))
  }

  function addEntry() {
    if (entries.length >= 5) return
    setEntries(prev => [...prev, emptyEntry()])
  }

  function removeEntry(idx) {
    if (entries.length <= 2) return
    setEntries(prev => prev.filter((_, i) => i !== idx))
    if (activeTab >= entries.length - 1) setActiveTab(entries.length - 2)
  }

  async function startAll() {
    const valid = entries.filter(e => e.value.trim())
    if (valid.length < 2) return

    setRunning(true)
    const reset = entries.map(e => ({
      ...e,
      state: e.value.trim() ? 'running' : 'idle',
      result: null,
      error: '',
      progress: e.value.trim() ? { step: 0, total: 5, message: '대기 중…' } : null,
    }))
    setEntries(reset)

    const promises = reset.map((entry, idx) => {
      if (!entry.value.trim()) return Promise.resolve()
      return new Promise(resolve => {
        const ws = new WebSocket(WS_URL)
        wsRefs.current[idx] = ws

        ws.onopen = () => ws.send(JSON.stringify({ address: entry.value.trim() }))

        ws.onmessage = (evt) => {
          const msg = JSON.parse(evt.data)
          if (msg.type === 'progress') {
            updateEntry(idx, { progress: { step: msg.step, total: msg.total, message: msg.message } })
          } else if (msg.type === 'result') {
            updateEntry(idx, { state: 'done', result: msg.data, progress: null })
            resolve()
          } else if (msg.type === 'error') {
            updateEntry(idx, { state: 'error', error: msg.message, progress: null })
            resolve()
          }
        }

        ws.onerror = () => {
          updateEntry(idx, { state: 'error', error: '서버 연결 실패', progress: null })
          resolve()
        }
      })
    })

    await Promise.all(promises)
    setRunning(false)
  }

  const doneEntries = entries.filter(e => e.state === 'done' && e.result)

  return (
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card section-panel">
        <p className="section-title">건물 주소 목록 (2~5개)</p>
        <div className="compare-input-list">
          {entries.map((entry, idx) => (
            <div key={entry.id} className="compare-addr-row">
              <span className="compare-num">{idx + 1}</span>
              <AddressInput
                value={entry.value}
                onChange={v => updateEntry(idx, { value: v })}
                onSubmit={startAll}
                disabled={running}
                placeholder={`건물 ${idx + 1} 주소 입력`}
              />
              {entry.state === 'running' && (
                <span className="status-dot running" style={{ marginLeft: 6 }} />
              )}
              {entry.state === 'done' && (
                <span className="status-dot done" style={{ marginLeft: 6 }} />
              )}
              {entry.state === 'error' && (
                <span className="status-dot error" style={{ marginLeft: 6 }} />
              )}
              {entries.length > 2 && (
                <button className="remove-btn" onClick={() => removeEntry(idx)} disabled={running} title="제거">×</button>
              )}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 12, marginTop: 14, flexWrap: 'wrap' }}>
          {entries.length < 5 && (
            <button className="add-addr-btn" onClick={addEntry} disabled={running}>
              + 건물 추가
            </button>
          )}
          <button
            className="analyze-btn"
            onClick={startAll}
            disabled={running || entries.filter(e => e.value.trim()).length < 2}
          >
            {running ? <><span className="spinner" /> 분석 중…</> : '전체 비교 분석'}
          </button>
        </div>
      </div>

      {entries.some(e => e.state === 'running') && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {entries.map((entry, idx) =>
            entry.state === 'running' && entry.progress ? (
              <div key={entry.id}>
                <p style={{ fontSize: 13, fontWeight: 600, marginBottom: 6, color: 'var(--text-2)' }}>
                  건물 {idx + 1}: {entry.value.slice(0, 30)}…
                </p>
                <ProgressBar
                  step={entry.progress.step}
                  total={entry.progress.total}
                  message={entry.progress.message}
                />
              </div>
            ) : null
          )}
        </div>
      )}

      {entries.some(e => e.state === 'error') && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {entries.map((entry, idx) =>
            entry.state === 'error' ? (
              <div key={entry.id} className="error-box">
                <strong>건물 {idx + 1} 오류</strong>{entry.error}
              </div>
            ) : null
          )}
        </div>
      )}

      {doneEntries.length >= 2 && (
        <CompareTable entries={doneEntries} />
      )}

      {doneEntries.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div className="compare-tabs-nav">
            {entries.map((entry, idx) =>
              entry.state === 'done' ? (
                <button
                  key={entry.id}
                  className={`compare-tab-btn ${activeTab === idx ? 'active' : ''}`}
                  onClick={() => setActiveTab(idx)}
                >
                  건물 {idx + 1}
                </button>
              ) : null
            )}
          </div>
          {entries[activeTab]?.state === 'done' && entries[activeTab]?.result && (
            <ResultCards
              summary={entries[activeTab].result.summary}
              htmlPath={entries[activeTab].result.html_path}
              pdfPath={entries[activeTab].result.pdf_path}
            />
          )}
        </div>
      )}

      {!running && doneEntries.length === 0 && entries.every(e => e.state === 'idle') && (
        <div className="empty-state">
          <div className="empty-icon">🏘️</div>
          <p>2개 이상의 건물 주소를 입력하고 비교 분석을 시작하세요.</p>
        </div>
      )}
    </div>
  )
}

function CompareTable({ entries }) {
  const rows = [
    {
      label: '시스템 용량 (kW)',
      get: s => s?.['태양광시스템']?.['총용량_kW'],
      fmt: v => v?.toFixed(1),
      best: 'max',
    },
    {
      label: '연간 발전량 (kWh)',
      get: s => s?.['태양광시스템']?.['연간발전량_kWh'],
      fmt: v => v?.toLocaleString(),
      best: 'max',
    },
    {
      label: '설치비 (만원)',
      get: s => s?.['경제성']?.['예상설치비_만원'],
      fmt: v => v?.toLocaleString(),
      best: 'min',
    },
    {
      label: '회수기간 (년)',
      get: s => s?.['경제성']?.['단순회수기간_년'],
      fmt: v => v?.toFixed(1),
      best: 'min',
    },
    {
      label: 'CO₂ 저감 (kg/년)',
      get: s => s?.['경제성']?.['연간CO2저감_kg'],
      fmt: v => v?.toLocaleString(),
      best: 'max',
    },
  ]

  return (
    <div className="compare-table-card">
      <div style={{ padding: '16px 20px 0', borderBottom: '1px solid var(--border)' }}>
        <p style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '0.7px', marginBottom: 12 }}>
          비교 요약
        </p>
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table className="compare-table">
          <thead>
            <tr>
              <th>항목</th>
              {entries.map((e, i) => (
                <th key={i}>
                  건물 {entries.indexOf(e) + 1}<br />
                  <span style={{ fontSize: 10, fontWeight: 400 }}>
                    {e.result?.summary?.['주소']?.slice(0, 18)}…
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => {
              const vals = entries.map(e => row.get(e.result?.summary))
              const numVals = vals.filter(v => v != null)
              const bestVal = numVals.length > 0
                ? (row.best === 'max' ? Math.max(...numVals) : Math.min(...numVals))
                : null
              return (
                <tr key={row.label}>
                  <td style={{ color: 'var(--text-2)', fontWeight: 500 }}>{row.label}</td>
                  {vals.map((v, i) => (
                    <td key={i} className={v != null && v === bestVal ? 'best' : ''}>
                      {v != null ? row.fmt(v) : '—'}
                      {v != null && v === bestVal && ' ★'}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

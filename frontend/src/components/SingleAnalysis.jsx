import { useState, useRef } from 'react'
import AddressInput from './AddressInput'
import ProgressBar from './ProgressBar'
import ResultCards from './ResultCards'

const WS_URL = 'ws://localhost:8001/ws/analyze'

export default function SingleAnalysis() {
  const [address, setAddress] = useState('')
  const [state, setState] = useState('idle') // idle | running | done | error
  const [progress, setProgress] = useState({ step: 0, total: 5, message: '' })
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const wsRef = useRef(null)

  function startAnalysis() {
    if (!address.trim() || state === 'running') return

    setState('running')
    setResult(null)
    setError('')
    setProgress({ step: 0, total: 5, message: '연결 중…' })

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => {
      ws.send(JSON.stringify({ address: address.trim() }))
    }

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      if (msg.type === 'progress') {
        setProgress({ step: msg.step, total: msg.total, message: msg.message })
      } else if (msg.type === 'result') {
        setResult(msg.data)
        setState('done')
      } else if (msg.type === 'error') {
        setError(msg.message)
        setState('error')
      }
    }

    ws.onerror = () => {
      setError('서버 연결에 실패했습니다. API 서버(localhost:8001)가 실행 중인지 확인하세요.')
      setState('error')
    }

    ws.onclose = (evt) => {
      if (state === 'running' && !evt.wasClean) {
        setError('서버 연결이 끊겼습니다.')
        setState('error')
      }
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="card section-panel">
        <p className="section-title">건물 주소 입력</p>
        <div className="address-row">
          <AddressInput
            value={address}
            onChange={setAddress}
            onSubmit={startAnalysis}
            disabled={state === 'running'}
          />
          <button
            className="analyze-btn"
            onClick={startAnalysis}
            disabled={!address.trim() || state === 'running'}
          >
            {state === 'running'
              ? <><span className="spinner" /> 분석 중…</>
              : '분석 시작'}
          </button>
        </div>
        <p style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
          엔터키로도 분석을 시작할 수 있습니다.
        </p>
      </div>

      {state === 'running' && (
        <ProgressBar
          step={progress.step}
          total={progress.total}
          message={progress.message}
        />
      )}

      {state === 'error' && (
        <div className="error-box">
          <strong>분석 오류</strong>
          {error}
        </div>
      )}

      {state === 'done' && result && (
        <ResultCards
          summary={result.summary}
          htmlPath={result.html_path}
          pdfPath={result.pdf_path}
        />
      )}

      {state === 'idle' && (
        <div className="empty-state card">
          <div className="empty-icon">🏠</div>
          <p>건물 주소를 입력하면 지붕 분석부터 보고서 생성까지 자동으로 진행됩니다.</p>
        </div>
      )}
    </div>
  )
}

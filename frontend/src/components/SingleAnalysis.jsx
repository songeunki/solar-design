import { useState, useRef } from 'react'
import AddressInput from './AddressInput'
import ProgressBar from './ProgressBar'
import ResultCards from './ResultCards'
import KakaoMap from './KakaoMap'

const WS_URL = 'ws://localhost:8001/ws/analyze'

export default function SingleAnalysis() {
  const [address,      setAddress]      = useState('')
  const [state,        setState]        = useState('idle') // idle | running | done | error
  const [progress,     setProgress]     = useState({ step: 0, total: 5, message: '' })
  const [result,       setResult]       = useState(null)
  const [error,        setError]        = useState('')
  const [markerLatLng, setMarkerLatLng] = useState(null)  // { lat, lng }
  const [markerResult, setMarkerResult] = useState(null)  // 분석 완료 후 지도 인포윈도우용
  const wsRef = useRef(null)

  function handleMapSelect(addr, lat, lng) {
    setAddress(addr)
    setMarkerLatLng({ lat, lng })
    setMarkerResult(null)
  }

  function startAnalysis() {
    if (!address.trim() || state === 'running') return

    setState('running')
    setResult(null)
    setError('')
    setMarkerResult(null)
    setProgress({ step: 0, total: 5, message: '연결 중…' })

    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => ws.send(JSON.stringify({ address: address.trim() }))

    ws.onmessage = (evt) => {
      const msg = JSON.parse(evt.data)
      if (msg.type === 'progress') {
        setProgress({ step: msg.step, total: msg.total, message: msg.message })
      } else if (msg.type === 'result') {
        setResult(msg.data)
        setMarkerResult(msg.data)
        // 지도 클릭이 아닌 직접 입력인 경우 서버 좌표로 마커 이동
        if (msg.data.lat && msg.data.lng) {
          setMarkerLatLng(prev =>
            prev ? prev : { lat: msg.data.lat, lng: msg.data.lng }
          )
        }
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
    <div className="split-layout">
      {/* 좌측 60% — 카카오맵 */}
      <div className="split-left">
        <KakaoMap
          onAddressSelect={handleMapSelect}
          markerLatLng={markerLatLng}
          markerResult={markerResult}
        />
      </div>

      {/* 우측 40% — 입력 + 결과 */}
      <div className="split-right">
        {/* 주소 입력 */}
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
            지도 클릭 또는 직접 입력 후 엔터
          </p>
        </div>

        {/* 프로그레스 */}
        {state === 'running' && (
          <ProgressBar
            step={progress.step}
            total={progress.total}
            message={progress.message}
          />
        )}

        {/* 오류 */}
        {state === 'error' && (
          <div className="error-box">
            <strong>분석 오류</strong>
            {error}
          </div>
        )}

        {/* 결과 */}
        {state === 'done' && result && (
          <ResultCards
            summary={result.summary}
            htmlPath={result.html_path}
            pdfPath={result.pdf_path}
          />
        )}

        {/* 초기 안내 */}
        {state === 'idle' && (
          <div className="empty-state card">
            <div className="empty-icon">🏠</div>
            <p>지도를 클릭하거나 주소를 입력하세요.</p>
          </div>
        )}
      </div>
    </div>
  )
}

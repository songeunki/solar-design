import { useState, useRef, useEffect } from 'react'
import AddressInput from './AddressInput'
import ProgressBar from './ProgressBar'
import ResultCards from './ResultCards'
import KakaoMap from './KakaoMap'

const _proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
const WS_URL = `${_proto}//${window.location.host}/ws/analyze`

export default function SingleAnalysis() {
  const [address,      setAddress]      = useState('')
  const [state,        setState]        = useState('idle')
  const [progress,     setProgress]     = useState({ step: 0, total: 5, message: '' })
  const [result,       setResult]       = useState(null)
  const [error,        setError]        = useState('')
  const [markerLatLng, setMarkerLatLng] = useState(null)
  const [markerResult, setMarkerResult] = useState(null)

  const wsRef    = useRef(null)
  const stateRef = useRef('idle')  // stale closure 방지용 ref

  // state와 ref를 동기화
  useEffect(() => { stateRef.current = state }, [state])

  function handleMapSelect(addr, lat, lng) {
    setAddress(addr)
    setMarkerLatLng({ lat, lng })
    setMarkerResult(null)
  }

  function startAnalysis() {
    if (!address.trim() || stateRef.current === 'running') return

    // 이전 WebSocket이 살아있으면 닫기
    if (wsRef.current && wsRef.current.readyState < 2) {
      wsRef.current.onclose = null  // 핸들러 제거 후 닫기 (오류 처리 방지)
      wsRef.current.close()
    }

    setState('running')
    stateRef.current = 'running'
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
        if (msg.data.lat && msg.data.lng) {
          setMarkerLatLng(prev => prev ?? { lat: msg.data.lat, lng: msg.data.lng })
        }
        setState('done')
        stateRef.current = 'done'
      } else if (msg.type === 'error') {
        setError(msg.message)
        setState('error')
        stateRef.current = 'error'
      }
    }

    ws.onerror = () => {
      setError('서버 연결에 실패했습니다. API 서버가 실행 중인지 확인하세요.')
      setState('error')
      stateRef.current = 'error'
    }

    ws.onclose = (evt) => {
      // stateRef로 현재 state를 읽어 stale closure 방지
      if (stateRef.current === 'running' && !evt.wasClean) {
        setError('서버 연결이 끊겼습니다.')
        setState('error')
        stateRef.current = 'error'
      }
    }
  }

  return (
    <div>
      <div className="sa-map">
        <KakaoMap
          onAddressSelect={handleMapSelect}
          markerLatLng={markerLatLng}
          markerResult={markerResult}
        />
        <div className="sa-overlay">
          <div className="sa-panel">
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
                  ? <><span className="spinner" />분석 중</>
                  : '분석 시작'}
              </button>
            </div>
            <p className="sa-hint">지도 클릭 또는 주소 직접 입력</p>
          </div>
        </div>
      </div>

      <div className="sa-body">
        {state === 'running' && (
          <ProgressBar step={progress.step} total={progress.total} message={progress.message} />
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
          <div className="empty-state">
            <div className="empty-icon">🗺️</div>
            <p>지도를 클릭하거나 주소를 입력해 분석을 시작하세요</p>
          </div>
        )}
      </div>
    </div>
  )
}

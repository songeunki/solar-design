import { useState, useRef, useCallback } from 'react';
import AddressInput from './AddressInput';
import ProgressBar from './ProgressBar';
import ResultCards from './ResultCards';
import KakaoMap from './KakaoMap';

const WS_BASE = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/^http/, 'ws')
  : `ws://${location.host}`;

export default function SingleAnalysis() {
  const [status, setStatus] = useState('idle'); // idle | loading | done | error
  const [step, setStep] = useState(0);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [markerPos, setMarkerPos] = useState(null);

  const wsRef = useRef(null);
  // stale closure 방지
  const statusRef = useRef(status);
  statusRef.current = status;

  const startAnalysis = useCallback(({ address }) => {
    if (statusRef.current === 'loading') return;

    setStatus('loading');
    setStep(0);
    setMessage('분석을 시작합니다...');
    setResult(null);
    setErrorMsg('');

    // WebSocket 연결
    const ws = new WebSocket(`${WS_BASE}/ws/analyze`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ address }));
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'progress') {
        setStep(data.step ?? 0);
        setMessage(data.message ?? '');
        if (data.lat && data.lng) {
          setMarkerPos({ lat: data.lat, lng: data.lng, label: address });
        }
      } else if (data.type === 'result') {
        setResult(data.result);
        setStatus('done');
        setStep(5);
        setMessage('분석 완료!');
      } else if (data.type === 'error') {
        setErrorMsg(data.message || '알 수 없는 오류가 발생했습니다.');
        setStatus('error');
      }
    };

    ws.onerror = () => {
      setErrorMsg('서버 연결에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      setStatus('error');
    };

    ws.onclose = () => {
      if (statusRef.current === 'loading') {
        setErrorMsg('서버 연결이 끊어졌습니다.');
        setStatus('error');
      }
    };
  }, []);

  const handleMapClick = useCallback((address) => {
    // 지도 클릭 시 주소 자동입력 — AddressInput으로 이벤트 전달할 방법이 없으므로
    // 여기서는 간단히 바로 분석 시작 (필요시 ref로 input 값 세팅 가능)
    startAnalysis({ address });
  }, [startAnalysis]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 입력 패널 */}
      <div className="input-panel">
        <div className="input-panel-title">
          🏠 단일 건물 태양광 분석
          <span className="badge badge-blue" style={{ marginLeft: 'auto' }}>
            640W 패널 기준
          </span>
        </div>
        <AddressInput
          onSubmit={startAnalysis}
          disabled={status === 'loading'}
        />
      </div>

      {/* 카카오맵 */}
      <KakaoMap
        markerPos={markerPos}
        onMapClick={handleMapClick}
        height={300}
      />

      {/* 프로그레스 */}
      {status === 'loading' && (
        <ProgressBar step={step} message={message} />
      )}

      {/* 에러 */}
      {status === 'error' && (
        <div
          style={{
            background: '#fff5f5',
            border: '1px solid #fed7d7',
            borderRadius: 'var(--radius-sm)',
            padding: '16px 20px',
            color: '#c53030',
            fontSize: 14,
            display: 'flex',
            alignItems: 'center',
            gap: 10,
          }}
        >
          ❌ {errorMsg}
          <button
            className="btn btn-sm"
            style={{ marginLeft: 'auto', background: '#fed7d7', color: '#c53030', border: 'none' }}
            onClick={() => setStatus('idle')}
          >
            다시 시도
          </button>
        </div>
      )}

      {/* 결과 */}
      {status === 'done' && result && (
        <>
          <div
            style={{
              background: 'var(--green-light)',
              border: '1px solid rgba(46,204,113,0.3)',
              borderRadius: 'var(--radius-sm)',
              padding: '12px 20px',
              color: '#276749',
              fontSize: 14,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            ✅ 분석이 완료되었습니다.
            <button
              className="btn btn-sm btn-outline"
              style={{ marginLeft: 'auto' }}
              onClick={() => { setStatus('idle'); setResult(null); }}
            >
              새 분석
            </button>
          </div>
          <ResultCards result={result} />
        </>
      )}
    </div>
  );
}

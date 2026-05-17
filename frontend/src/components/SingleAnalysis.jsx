import { useState, useRef, useCallback } from 'react';
import AddressInput from './AddressInput';
import ProgressBar from './ProgressBar';
import ResultTabs from './ResultTabs';
import KakaoMap from './KakaoMap';

const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;

export default function SingleAnalysis() {
  const [status, setStatus]               = useState('idle');
  const [step, setStep]                   = useState(0);
  const [message, setMessage]             = useState('');
  const [result, setResult]               = useState(null);
  const [errorMsg, setErrorMsg]           = useState('');
  const [markerPos, setMarkerPos]         = useState(null);
  const [buildingPolygon, setBuildingPolygon] = useState(null);

  const wsRef     = useRef(null);
  const statusRef = useRef(status);
  statusRef.current = status;

  const startAnalysis = useCallback(({ address, azimuth_override = null }) => {
    if (statusRef.current === 'loading') return;

    if (wsRef.current && wsRef.current.readyState < 2) {
      wsRef.current.onclose = null;
      wsRef.current.close();
    }

    setStatus('loading');
    setStep(0);
    setMessage('연결 중…');
    setResult(null);
    setErrorMsg('');
    setBuildingPolygon(null);

    if (window.kakao?.maps?.services) {
      const geocoder = new window.kakao.maps.services.Geocoder();
      geocoder.addressSearch(address.trim(), (res, st) => {
        if (st === window.kakao.maps.services.Status.OK && res[0]) {
          setMarkerPos({ lat: parseFloat(res[0].y), lng: parseFloat(res[0].x) });
        }
      });
    }

    const ws = new WebSocket(`${WS_BASE}/ws/analyze`);
    wsRef.current = ws;

    ws.onopen = () => ws.send(JSON.stringify({ address, azimuth_override }));

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'progress') {
        setStep(msg.step ?? 0);
        setMessage(msg.message ?? '');
      } else if (msg.type === 'result') {
        setResult(msg.data);
        if (msg.data?.lat && msg.data?.lng) {
          setMarkerPos({ lat: msg.data.lat, lng: msg.data.lng });
        }
        if (msg.data?.panel_layout?.roof_polygon) {
          setBuildingPolygon(msg.data.panel_layout.roof_polygon);
        }
        setStatus('done');
        setStep(5);
        setMessage('분석 완료!');
      } else if (msg.type === 'error') {
        setErrorMsg(msg.message || '알 수 없는 오류가 발생했습니다.');
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

  const handleReset = useCallback(() => {
    setStatus('idle');
    setResult(null);
    setMarkerPos(null);
    setBuildingPolygon(null);
  }, []);

  const isDone = status === 'done' && result;

  return (
    <div className={`analysis-layout${isDone ? ' analysis-layout--wide' : ''}`}>

      {/* ── 사이드바: 입력 + 지도(분석 전) ── */}
      <div className="analysis-sidebar">
        <div className="input-panel">
          <div className="input-panel-title">🏠 단일 건물 태양광 분석</div>
          <AddressInput onSubmit={startAnalysis} disabled={status === 'loading'} />
          <p style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
            {isDone
              ? '탭 1의 위성지도를 클릭하거나 새 주소를 입력하면 재분석합니다.'
              : '주소를 입력하거나 지도를 클릭해 분석을 시작하세요'}
          </p>
        </div>

        {/* 분석 전에는 사이드바에 지도 표시 (클릭하여 분석 시작) */}
        {!isDone && (
          <KakaoMap
            markerPos={markerPos}
            onMapClick={(addr) => startAnalysis({ address: addr })}
            buildingPolygon={buildingPolygon}
            panelLayout={null}
          />
        )}
      </div>

      {/* ── 메인 콘텐츠 ── */}
      <div className="analysis-content">

        {status === 'idle' && (
          <div className="idle-state">
            <div className="idle-icon">☀️</div>
            <p className="idle-title">분석 준비 완료</p>
            <p className="idle-desc">
              좌측에서 주소를 입력하거나 지도를 클릭해 분석을 시작하세요
            </p>
          </div>
        )}

        {status === 'loading' && <ProgressBar step={step} message={message} />}

        {status === 'error' && (
          <div className="alert-box alert-error">
            <span>❌ {errorMsg}</span>
            <button className="btn btn-sm"
              style={{ marginLeft: 'auto', background: '#fed7d7', color: '#c53030', border: 'none', flexShrink: 0 }}
              onClick={() => setStatus('idle')}>
              다시 시도
            </button>
          </div>
        )}

        {isDone && (
          <ResultTabs
            result={result}
            markerPos={markerPos}
            buildingPolygon={buildingPolygon}
            onMapClick={(addr) => startAnalysis({ address: addr })}
            onReset={handleReset}
          />
        )}

      </div>
    </div>
  );
}

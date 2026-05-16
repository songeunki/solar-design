import { useState, useRef, useCallback } from 'react';
import AddressInput from './AddressInput';
import ProgressBar from './ProgressBar';
import ResultCards from './ResultCards';
import KakaoMap from './KakaoMap';

const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;

export default function SingleAnalysis() {
  const [status, setStatus] = useState('idle');
  const [step, setStep] = useState(0);
  const [message, setMessage] = useState('');
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [markerPos, setMarkerPos] = useState(null);
  const [buildingPolygon, setBuildingPolygon] = useState(null);

  const wsRef = useRef(null);
  const statusRef = useRef(status);
  statusRef.current = status;

  const startAnalysis = useCallback(({ address }) => {
    if (statusRef.current === 'loading') return;

    // 이전 WebSocket 정리
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

    // 분석 시작 즉시 Kakao 지오코딩으로 지도 마커 선제 이동
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

    ws.onopen = () => ws.send(JSON.stringify({ address }));

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

  return (
    <div className="analysis-layout">

      {/* ── 사이드바: 입력 패널 + 지도 ── */}
      <div className="analysis-sidebar">
        <div className="input-panel">
          <div className="input-panel-title">
            🏠 단일 건물 태양광 분석
          </div>
          <AddressInput
            onSubmit={startAnalysis}
            disabled={status === 'loading'}
          />
          <p style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
            지도를 클릭하면 해당 위치로 바로 분석을 시작합니다
          </p>
        </div>

        <KakaoMap
          markerPos={markerPos}
          onMapClick={(addr) => startAnalysis({ address: addr })}
          buildingPolygon={buildingPolygon}
          panelLayout={status === 'done' ? result?.panel_layout : null}
        />
      </div>

      {/* ── 콘텐츠: 결과 영역 ── */}
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

        {status === 'loading' && (
          <ProgressBar step={step} message={message} />
        )}

        {status === 'error' && (
          <div className="alert-box alert-error">
            <span>❌ {errorMsg}</span>
            <button
              className="btn btn-sm"
              style={{ marginLeft: 'auto', background: '#fed7d7', color: '#c53030', border: 'none', flexShrink: 0 }}
              onClick={() => setStatus('idle')}
            >
              다시 시도
            </button>
          </div>
        )}

        {status === 'done' && result && (
          <>
            <div className="alert-box alert-success">
              ✅ 분석이 완료되었습니다.
              <button
                className="btn btn-sm btn-outline"
                style={{ marginLeft: 'auto', flexShrink: 0 }}
                onClick={() => { setStatus('idle'); setResult(null); setMarkerPos(null); setBuildingPolygon(null); }}
              >
                새 분석
              </button>
            </div>
            <ResultCards result={result} />
          </>
        )}

      </div>
    </div>
  );
}

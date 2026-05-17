import { useState, useRef, useCallback, useEffect } from 'react';
import AddressInput from './AddressInput';
import ProgressBar from './ProgressBar';
import ResultTabs from './ResultTabs';
import KakaoMap from './KakaoMap';

const WS_BASE = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;

export default function SingleAnalysis({ onResultChange }) {
  const [headerH, setHeaderH] = useState(100);
  useEffect(() => {
    const header = document.querySelector('.app-header-dark');
    if (header) setHeaderH(header.offsetHeight);
  }, []);

  const [showModal, setShowModal]         = useState(false);
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
    setShowModal(false);

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
        onResultChange?.(true);
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
  }, [onResultChange]);

  const handleReset = useCallback(() => {
    setStatus('idle');
    setResult(null);
    setMarkerPos(null);
    setBuildingPolygon(null);
    onResultChange?.(false);
  }, [onResultChange]);

  const isDone = status === 'done' && result;
  const { system = {}, financial = {} } = result || {};

  return (
    <>
      {/* ── 입력 모달 ── */}
      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-box" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <i className="fa-solid fa-magnifying-glass"></i>
              <span>분석 시작</span>
              <button className="modal-close" onClick={() => setShowModal(false)}>✕</button>
            </div>
            <div className="modal-body">
              <AddressInput onSubmit={startAnalysis} disabled={false} />
            </div>
          </div>
        </div>
      )}

      {/* ── 웰컴 스크린 ── */}
      {status === 'idle' && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: `calc(100dvh - ${headerH}px)`,
          width: '100%',
        }}>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: '16px',
            padding: '0 24px',
          }}>
            <div className="welcome-icon-wrap">
              <i className="fa-solid fa-solar-panel"></i>
            </div>
            <h1 className="welcome-title">AI 태양광 입지 분석</h1>
            <p className="welcome-sub">주소 하나로 수익성, 설계, 규제까지 자동 분석</p>
            <button className="btn-start-analysis" onClick={() => setShowModal(true)}>
              <i className="fa-solid fa-magnifying-glass"></i>
              분석 시작하기
            </button>
          </div>
        </div>
      )}

      {/* ── 로딩 ── */}
      {status === 'loading' && (
        <div className="loading-screen">
          <ProgressBar step={step} message={message} />
        </div>
      )}

      {/* ── 에러 ── */}
      {status === 'error' && (
        <div className="error-screen">
          <div className="alert-box alert-error">
            <span>❌ {errorMsg}</span>
            <button
              className="btn btn-sm"
              style={{ marginLeft: 'auto', background: '#fed7d7', color: '#c53030', border: 'none', flexShrink: 0 }}
              onClick={() => { setStatus('idle'); onResultChange?.(false); }}
            >
              다시 시도
            </button>
          </div>
        </div>
      )}

      {/* ── 결과 대시보드 ── */}
      {isDone && (
        <div className="dashboard-layout">
          {/* KPI 바 */}
          <div className="dashboard-kpi-bar">
            {[
              {
                icon: 'fa-bolt',
                label: '설치 용량',
                value: system.totalKw ?? '-',
                unit: 'kW',
                color: 'accent-blue',
              },
              {
                icon: 'fa-sun',
                label: '연간 발전량',
                value: system.yearlyTotal?.toLocaleString() ?? '-',
                unit: 'kWh',
                color: 'accent-green',
              },
              {
                icon: 'fa-coins',
                label: '연간 수익',
                value: financial.yearlyRevenue
                  ? `${Math.round(financial.yearlyRevenue / 10000).toLocaleString()}만`
                  : '-',
                unit: '원',
                color: 'accent-amber',
              },
              {
                icon: 'fa-clock-rotate-left',
                label: '투자 회수',
                value: financial.paybackYear ?? '-',
                unit: '년',
                color: 'accent-blue',
              },
            ].map((k, i) => (
              <div key={i} className={`dashboard-kpi-card ${k.color}`}>
                <div className="dash-kpi-icon">
                  <i className={`fa-solid ${k.icon}`}></i>
                </div>
                <div className="dash-kpi-text">
                  <div className="dash-kpi-value">
                    {k.value}<span className="dash-kpi-unit">{k.unit}</span>
                  </div>
                  <div className="dash-kpi-label">{k.label}</div>
                </div>
              </div>
            ))}
          </div>

          {/* 2컬럼: 지도 + 탭 */}
          <div className="dashboard-body">
            <div className="dashboard-map">
              <KakaoMap
                markerPos={markerPos}
                onMapClick={(addr) => startAnalysis({ address: addr })}
                buildingPolygon={buildingPolygon}
                panelLayout={result.panel_layout}
                height={480}
              />
            </div>
            <div className="dashboard-tabs">
              <ResultTabs
                result={result}
                markerPos={markerPos}
                buildingPolygon={buildingPolygon}
                onMapClick={(addr) => startAnalysis({ address: addr })}
                onReset={handleReset}
              />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

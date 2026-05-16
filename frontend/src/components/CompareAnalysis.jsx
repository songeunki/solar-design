import { useState, useRef, useCallback } from 'react';
import AddressInput from './AddressInput';
import ProgressBar from './ProgressBar';
import KakaoMap from './KakaoMap';
import MonthlyChart from './MonthlyChart';
import DownloadButtons from './DownloadButtons';

const WS_BASE = import.meta.env.VITE_API_URL
  ? import.meta.env.VITE_API_URL.replace(/^http/, 'ws')
  : `ws://${location.host}`;

export default function CompareAnalysis() {
  const [addresses, setAddresses] = useState(['', '']);
  const [status, setStatus] = useState('idle');
  const [step, setStep] = useState(0);
  const [message, setMessage] = useState('');
  const [results, setResults] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const [markers, setMarkers] = useState([]);

  const wsRef = useRef(null);
  const statusRef = useRef(status);
  statusRef.current = status;

  const addAddress = () => {
    if (addresses.length < 4) setAddresses([...addresses, '']);
  };

  const removeAddress = (i) => {
    if (addresses.length > 2) {
      setAddresses(addresses.filter((_, idx) => idx !== i));
    }
  };

  const updateAddress = (i, val) => {
    const next = [...addresses];
    next[i] = val;
    setAddresses(next);
  };

  const startCompare = useCallback(() => {
    const valid = addresses.filter((a) => a.trim());
    if (valid.length < 2) return;
    if (statusRef.current === 'loading') return;

    setStatus('loading');
    setStep(0);
    setMessage('비교 분석을 시작합니다...');
    setResults(null);
    setErrorMsg('');

    const ws = new WebSocket(`${WS_BASE}/ws/compare`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ addresses: valid }));
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'progress') {
        setStep(data.step ?? 0);
        setMessage(data.message ?? '');
        if (data.markers) setMarkers(data.markers);
      } else if (data.type === 'result') {
        setResults(data.results);
        setStatus('done');
        setStep(5);
      } else if (data.type === 'error') {
        setErrorMsg(data.message || '오류가 발생했습니다.');
        setStatus('error');
      }
    };

    ws.onerror = () => { setErrorMsg('서버 연결 실패'); setStatus('error'); };
    ws.onclose = () => {
      if (statusRef.current === 'loading') {
        setErrorMsg('연결이 끊어졌습니다.'); setStatus('error');
      }
    };
  }, [addresses]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* 주소 입력 */}
      <div className="input-panel">
        <div className="input-panel-title">
          ⚖️ 복수 건물 비교 분석
          <span className="badge badge-orange" style={{ marginLeft: 'auto' }}>
            최대 4개 건물
          </span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {addresses.map((addr, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <div
                style={{
                  width: 26, height: 26, borderRadius: '50%',
                  background: i === 0 ? 'var(--blue)' : 'var(--orange)',
                  color: 'white', display: 'flex', alignItems: 'center',
                  justifyContent: 'center', fontSize: 13, fontWeight: 700, flexShrink: 0,
                }}
              >
                {i + 1}
              </div>
              <input
                className="input-field"
                style={{ flex: 1 }}
                value={addr}
                onChange={(e) => updateAddress(i, e.target.value)}
                placeholder={`건물 ${i + 1} 주소`}
                disabled={status === 'loading'}
              />
              {addresses.length > 2 && (
                <button
                  className="btn btn-sm"
                  style={{ background: '#fed7d7', color: '#c53030', border: 'none' }}
                  onClick={() => removeAddress(i)}
                  disabled={status === 'loading'}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
          {addresses.length < 4 && (
            <button className="btn btn-outline btn-sm" onClick={addAddress} disabled={status === 'loading'}>
              + 건물 추가
            </button>
          )}
          <button
            className="btn btn-primary"
            style={{ marginLeft: 'auto' }}
            onClick={startCompare}
            disabled={
              status === 'loading' ||
              addresses.filter((a) => a.trim()).length < 2
            }
          >
            {status === 'loading' ? (
              <><span className="spinner" /> 비교 중...</>
            ) : (
              '🔍 비교 분석 시작'
            )}
          </button>
        </div>
      </div>

      {/* 지도 */}
      <KakaoMap markers={markers} height={280} />

      {/* 프로그레스 */}
      {status === 'loading' && <ProgressBar step={step} message={message} />}

      {/* 에러 */}
      {status === 'error' && (
        <div style={{
          background: '#fff5f5', border: '1px solid #fed7d7',
          borderRadius: 'var(--radius-sm)', padding: '16px 20px',
          color: '#c53030', fontSize: 14,
        }}>
          ❌ {errorMsg}
        </div>
      )}

      {/* 결과 비교 */}
      {status === 'done' && results && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{
            background: 'var(--green-light)', border: '1px solid rgba(46,204,113,0.3)',
            borderRadius: 'var(--radius-sm)', padding: '12px 20px',
            color: '#276749', fontSize: 14,
          }}>
            ✅ 비교 분석이 완료되었습니다. ({results.length}개 건물)
          </div>

          {/* 건물별 결과 그리드 */}
          <div className="compare-grid">
            {results.map((r, i) => (
              <div key={i} className="card" style={{
                borderTop: `3px solid ${i === 0 ? 'var(--blue)' : 'var(--orange)'}`,
              }}>
                <div className="section-header">
                  <div
                    className="section-title-dot"
                    style={{ background: i === 0 ? 'var(--blue)' : 'var(--orange)' }}
                  />
                  <span className="section-title">
                    건물 {i + 1}: {r.building?.name || r.address}
                  </span>
                </div>

                {/* KPI 요약 */}
                <div style={{ padding: '12px 24px', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {[
                    { label: '설치 용량', val: `${r.system?.totalKw ?? '-'} kW` },
                    { label: '연간 발전', val: `${r.system?.yearlyTotal?.toLocaleString() ?? '-'} kWh` },
                    { label: '회수 기간', val: `${r.financial?.paybackYear ?? '-'}년` },
                  ].map((k, j) => (
                    <div key={j} style={{
                      flex: 1, minWidth: 90,
                      background: 'var(--bg)', borderRadius: 8,
                      padding: '10px 12px',
                    }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>
                        {k.label}
                      </div>
                      <div style={{
                        fontSize: 16, fontWeight: 700,
                        color: i === 0 ? 'var(--blue)' : 'var(--orange)',
                      }}>
                        {k.val}
                      </div>
                    </div>
                  ))}
                </div>

                {/* 차트 */}
                <MonthlyChart data={r.monthly_data || []} />

                {/* 다운로드 */}
                <DownloadButtons reportUrl={r.report_url} pdfUrl={r.pdf_url} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

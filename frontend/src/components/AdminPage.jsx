import { useState, useEffect } from 'react';
import { HTTP_BASE } from '../lib/api';

const FIELDS = [
  {
    section: '📐 패널 규격',
    items: [
      { key: 'panel_watt',           label: '패널 출력',    unit: 'W',       step: 1,     min: 100,  max: 1000, hint: '모듈 1장의 정격 출력 (현재 640W)' },
      { key: 'panel_efficiency_pct', label: '패널 효율',    unit: '%',       step: 0.1,   min: 1,    max: 30,   hint: '발전 효율 (기본 20%)' },
      { key: 'system_loss_pct',      label: '시스템 손실',  unit: '%',       step: 0.1,   min: 0,    max: 30,   hint: '배선·인버터 등 종합 손실 (기본 14%)' },
      { key: 'panel_width_m',        label: '패널 단변(폭)', unit: 'm',      step: 0.001, min: 0.1,  max: 3,    hint: '패널 짧은 쪽 치수 (1.134 m)' },
      { key: 'panel_height_m',       label: '패널 장변(높이)', unit: 'm',    step: 0.001, min: 0.1,  max: 3,    hint: '패널 긴 쪽 치수 (2.094 m)' },
    ],
  },
  {
    section: '💰 수익 · 비용 기준',
    items: [
      { key: 'revenue_per_kwh', label: 'kWh당 수익',  unit: '원/kWh',  step: 1, min: 0, hint: '계통 판매 단가 (기본 150원)' },
      { key: 'cost_per_kw',     label: 'kW당 설치비', unit: '만원/kW', step: 1, min: 0, hint: '시스템 설치 단가 (기본 150만원)' },
    ],
  },
];

const DEFAULTS_FORM = {
  panel_watt:           640,
  panel_efficiency_pct: 20.0,
  system_loss_pct:      14.0,
  panel_width_m:        1.134,
  panel_height_m:       2.094,
  revenue_per_kwh:      150,
  cost_per_kw:          150,
};

function apiToForm(data) {
  return {
    panel_watt:           data.panel_watt           ?? DEFAULTS_FORM.panel_watt,
    panel_efficiency_pct: +((data.panel_efficiency ?? 0.20) * 100).toFixed(2),
    system_loss_pct:      +((data.system_loss      ?? 0.14) * 100).toFixed(2),
    panel_width_m:        data.panel_width_m        ?? DEFAULTS_FORM.panel_width_m,
    panel_height_m:       data.panel_height_m       ?? DEFAULTS_FORM.panel_height_m,
    revenue_per_kwh:      data.revenue_per_kwh      ?? DEFAULTS_FORM.revenue_per_kwh,
    cost_per_kw:          data.cost_per_kw          ?? DEFAULTS_FORM.cost_per_kw,
  };
}

function formToApi(form, password) {
  return {
    password,
    panel_watt:       parseFloat(form.panel_watt),
    panel_efficiency: parseFloat(form.panel_efficiency_pct) / 100,
    system_loss:      parseFloat(form.system_loss_pct) / 100,
    panel_width_m:    parseFloat(form.panel_width_m),
    panel_height_m:   parseFloat(form.panel_height_m),
    revenue_per_kwh:  parseFloat(form.revenue_per_kwh),
    cost_per_kw:      parseFloat(form.cost_per_kw),
  };
}

export default function AdminPage() {
  const [phase,    setPhase]    = useState('login');   // login | config | logs
  const [pw,       setPw]       = useState('');
  const [pwError,  setPwError]  = useState('');
  const [form,     setForm]     = useState(DEFAULTS_FORM);
  const [status,   setStatus]   = useState('');        // '' | 'saving' | 'saved' | 'error'
  const [loading,  setLoading]  = useState(false);
  const [logs,     setLogs]     = useState(null);      // null | {total_count, logs}
  const [logsLoading, setLogsLoading] = useState(false);

  // ── 로그인 ───────────────────────────────────────────────────────────────────
  const handleLogin = async () => {
    setPwError('');
    setLoading(true);
    try {
      const res = await fetch(`${HTTP_BASE}/api/admin/config?password=${encodeURIComponent(pw)}`);
      if (res.status === 401) { setPwError('비밀번호가 올바르지 않습니다.'); return; }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setForm(apiToForm(data));
      setPhase('config');
    } catch (e) {
      setPwError(`서버 오류: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  // ── 로그 조회 ────────────────────────────────────────────────────────────────
  const fetchLogs = async () => {
    setLogsLoading(true);
    try {
      const res = await fetch(`${HTTP_BASE}/api/admin/logs?password=${encodeURIComponent(pw)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setLogs(await res.json());
    } catch (e) {
      setLogs({ total_count: 0, logs: [], error: e.message });
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    if (phase === 'logs' && logs === null) fetchLogs();
  }, [phase]);

  const handleKeyDown = (e) => { if (e.key === 'Enter') handleLogin(); };

  // ── 저장 ─────────────────────────────────────────────────────────────────────
  const handleSave = async () => {
    setStatus('saving');
    try {
      const res = await fetch(`${HTTP_BASE}/api/admin/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formToApi(form, pw)),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      setStatus('saved');
      setTimeout(() => setStatus(''), 2500);
    } catch (e) {
      setStatus('error:' + e.message);
    }
  };

  const update = (key, val) => setForm(f => ({ ...f, [key]: val }));

  // ── 헤더 ─────────────────────────────────────────────────────────────────────
  const Header = () => (
    <header style={{
      background: 'var(--blue)', padding: '0 24px',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      position: 'sticky', top: 0, zIndex: 100, minHeight: 60,
      boxShadow: '0 2px 12px rgba(30,111,217,0.25)', flexWrap: 'wrap', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
        <div style={{
          width: 32, height: 32, background: 'rgba(255,255,255,0.2)',
          borderRadius: 8, display: 'flex', alignItems: 'center',
          justifyContent: 'center', fontSize: 18, flexShrink: 0,
        }}><i className="fa-solid fa-solar-panel" style={{color:'white', marginRight:0}}></i></div>
        <span style={{ color: 'white', fontSize: 17, fontWeight: 700, letterSpacing: '-0.3px', whiteSpace: 'nowrap' }}>
          SolarDesign AI
        </span>
      </div>
      {phase !== 'login' && (
        <div style={{ display: 'flex', gap: 4 }}>
          {[{key:'config', label:'⚙️ 기준값 설정'}, {key:'logs', label:'📋 분석 로그'}].map(t => (
            <button key={t.key} onClick={() => setPhase(t.key)} style={{
              background: phase === t.key ? 'rgba(255,255,255,0.25)' : 'transparent',
              border: '1px solid rgba(255,255,255,0.3)', color: 'white',
              borderRadius: 8, padding: '6px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
            }}>{t.label}</button>
          ))}
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
        <a href="/" style={{ color: 'rgba(255,255,255,0.8)', fontSize: 12, textDecoration: 'none', whiteSpace: 'nowrap' }}>
          <i className="fa-solid fa-arrow-left"></i> 메인으로
        </a>
      </div>
    </header>
  );

  // ── 로그인 화면 ───────────────────────────────────────────────────────────────
  if (phase === 'login') {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', fontFamily: "'Noto Sans KR', sans-serif" }}>
        <Header />
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          minHeight: 'calc(100vh - 60px)', padding: 24,
        }}>
          <div style={{
            background: 'white', borderRadius: 16, padding: '40px 36px',
            width: '100%', maxWidth: 400,
            boxShadow: '0 10px 40px rgba(0,0,0,0.1)',
          }}>
            <div style={{ textAlign: 'center', marginBottom: 32 }}>
              <div style={{
                width: 64, height: 64, background: 'var(--blue-light)',
                borderRadius: '50%', display: 'flex', alignItems: 'center',
                justifyContent: 'center', fontSize: 28, margin: '0 auto 16px',
              }}>🔐</div>
              <h2 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
                관리자 인증
              </h2>
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                설정 페이지에 접근하려면 비밀번호를 입력하세요.
              </p>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                비밀번호
              </label>
              <input
                type="password"
                className="input-field"
                placeholder="관리자 비밀번호 입력"
                value={pw}
                onChange={e => { setPw(e.target.value); setPwError(''); }}
                onKeyDown={handleKeyDown}
                autoFocus
                style={{ width: '100%' }}
              />
              {pwError && (
                <div style={{ marginTop: 8, fontSize: 12, color: '#e53e3e', display: 'flex', gap: 4 }}>
                  ⚠️ {pwError}
                </div>
              )}
            </div>

            <button
              className="btn btn-primary"
              onClick={handleLogin}
              disabled={loading || !pw}
              style={{ width: '100%', padding: '12px', fontSize: 15, fontWeight: 700 }}
            >
              {loading ? <><span className="spinner" style={{ marginRight: 8 }} />확인 중…</> : '로그인'}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── 로그 화면 ─────────────────────────────────────────────────────────────────
  if (phase === 'logs') {
    const rows = logs?.logs ?? [];
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg)', fontFamily: "'Noto Sans KR', sans-serif" }}>
        <Header />
        <main style={{ maxWidth: 1100, margin: '0 auto', padding: '32px 24px 64px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
            <div>
              <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
                분석 로그
              </h1>
              <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                총 <strong>{logs?.total_count ?? '…'}</strong>건의 분석 기록
              </p>
            </div>
            <button className="btn btn-outline" onClick={() => { setLogs(null); fetchLogs(); }} disabled={logsLoading}
              style={{ fontSize: 13, padding: '8px 18px' }}>
              {logsLoading ? <><span className="spinner" style={{ marginRight: 6 }} />로딩 중…</> : <><i className="fa-solid fa-arrows-rotate"></i> 새로고침</>}
            </button>
          </div>

          {logs?.error && (
            <div style={{ background: '#fff5f5', border: '1px solid #fed7d7', borderRadius: 8, padding: '12px 16px', marginBottom: 16, color: '#c53030', fontSize: 13 }}>
              ⚠️ {logs.error}
            </div>
          )}

          <div style={{ overflowX: 'auto', borderRadius: 12, border: '1px solid var(--border)', background: 'white' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: 'var(--bg)', borderBottom: '2px solid var(--border)' }}>
                  {['#', '시간 (UTC)', 'IP', '주소', '용량(kW)', '연간발전(kWh)', '회수기간(년)'].map(h => (
                    <th key={h} style={{ padding: '12px 14px', textAlign: 'left', fontWeight: 700, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr><td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    {logsLoading ? '로딩 중…' : '분석 기록이 없습니다.'}
                  </td></tr>
                )}
                {rows.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid var(--border)', background: i % 2 === 0 ? 'white' : 'var(--bg)' }}>
                    <td style={{ padding: '10px 14px', color: 'var(--text-muted)', fontWeight: 600 }}>{(logs?.total_count ?? rows.length) - i}</td>
                    <td style={{ padding: '10px 14px', whiteSpace: 'nowrap' }}>{r.timestamp?.replace('T', ' ')}</td>
                    <td style={{ padding: '10px 14px', fontFamily: 'monospace', fontSize: 12 }}>{r.ip}</td>
                    <td style={{ padding: '10px 14px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.address}>{r.address}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 600 }}>{r.capacity_kw}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>{r.annual_kwh?.toLocaleString?.()}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'right' }}>{r.roi_years}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </main>
      </div>
    );
  }

  // ── 설정 화면 ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', fontFamily: "'Noto Sans KR', sans-serif" }}>
      <Header />

      <main style={{ maxWidth: 720, margin: '0 auto', padding: '32px 24px 64px' }}>
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: 'var(--text-primary)', marginBottom: 4 }}>
            기준값 설정
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            태양광 분석에 사용되는 기준값을 설정합니다. 저장 후 다음 분석부터 적용됩니다.
          </p>
        </div>

        {FIELDS.map(group => (
          <div key={group.section} className="card" style={{ marginBottom: 20, padding: 0, overflow: 'hidden' }}>
            {/* 섹션 헤더 */}
            <div style={{
              padding: '14px 24px', borderBottom: '1px solid var(--border)',
              background: 'var(--bg)', display: 'flex', alignItems: 'center',
            }}>
              <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
                {group.section}
              </span>
            </div>

            {/* 필드 목록 */}
            <div style={{ padding: '8px 0' }}>
              {group.items.map(f => (
                <div key={f.key} style={{
                  display: 'grid',
                  gridTemplateColumns: '180px 1fr 90px',
                  alignItems: 'center',
                  gap: 12, padding: '12px 24px',
                  borderBottom: '1px solid var(--border)',
                }}>
                  {/* 레이블 */}
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                      {f.label}
                    </div>
                    {f.hint && (
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                        {f.hint}
                      </div>
                    )}
                  </div>

                  {/* 입력 */}
                  <input
                    type="number"
                    className="input-field"
                    value={form[f.key]}
                    onChange={e => update(f.key, e.target.value)}
                    step={f.step}
                    min={f.min}
                    max={f.max}
                    style={{ textAlign: 'right', fontSize: 15, fontWeight: 600 }}
                  />

                  {/* 단위 */}
                  <div style={{
                    fontSize: 13, color: 'var(--text-muted)', fontWeight: 500,
                    textAlign: 'left', paddingLeft: 4,
                  }}>
                    {f.unit}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* 저장 버튼 + 상태 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 8 }}>
          <button
            className="btn btn-primary"
            onClick={handleSave}
            disabled={status === 'saving'}
            style={{ padding: '13px 40px', fontSize: 15, fontWeight: 700, borderRadius: 10 }}
          >
            {status === 'saving'
              ? <><span className="spinner" style={{ marginRight: 8 }} />저장 중…</>
              : <><i className="fa-solid fa-floppy-disk"></i> 저장하기</>}
          </button>

          {status === 'saved' && (
            <div style={{ color: '#38a169', fontWeight: 600, fontSize: 14 }}>
              ✅ 저장되었습니다.
            </div>
          )}
          {status.startsWith('error:') && (
            <div style={{ color: '#e53e3e', fontSize: 13 }}>
              ⚠️ {status.slice(6)}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

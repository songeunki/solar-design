import { useState, lazy, Suspense } from 'react';
import KakaoMap from './KakaoMap';
import MonthlyChart from './MonthlyChart';
import SolarAltitudeChart from './SolarAltitudeChart';
import PanelLayoutViewer from './PanelLayoutViewer';
import BuildingInfo from './BuildingInfo';
import DownloadButtons from './DownloadButtons';

const PanelLayout3D = lazy(() => import('./PanelLayout3D'));

const TABS = [
  { id: 'location', icon: '📍', label: '입지 분석' },
  { id: 'revenue',  icon: '💰', label: '수익 분석' },
  { id: 'design',   icon: '🔧', label: '설계 분석' },
  { id: 'ai',       icon: '🤖', label: 'AI 종합 평가' },
];

// ── 공통 KPI 카드 ────────────────────────────────────────────────────────────
function KpiCard({ icon, label, value, unit, color = 'blue' }) {
  return (
    <div className="kpi-card">
      <div className="kpi-text">
        <div className="kpi-label">{label}</div>
        <div className="kpi-value">
          {value}<span className="kpi-unit">{unit}</span>
        </div>
      </div>
      <div className={`kpi-icon ${color}`}>{icon}</div>
    </div>
  );
}

// ── 20년 누적 수익 SVG 차트 ───────────────────────────────────────────────────
function CumulativeChart({ installCost, yearlyRevenue, paybackYear }) {
  const W = 600, H = 230;
  const PAD = { top: 28, right: 24, bottom: 40, left: 84 };
  const cW = W - PAD.left - PAD.right;
  const cH = H - PAD.top - PAD.bottom;

  const vals = Array.from({ length: 21 }, (_, y) => -installCost + y * yearlyRevenue);
  const minV = Math.min(...vals), maxV = Math.max(...vals);
  const range = maxV - minV || 1;

  const toX = y => PAD.left + (y / 20) * cW;
  const toY = v => PAD.top + cH - ((v - minV) / range) * cH;

  const zeroY = toY(0);
  const pbX   = paybackYear != null ? toX(paybackYear) : null;

  const pts = vals.map((v, y) => `${toX(y)},${toY(v)}`).join(' ');

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(r => ({
    v: minV + r * range,
    y: PAD.top + (1 - r) * cH,
  }));

  const fmt = v => {
    const m = Math.round(v / 10000);
    return m >= 0 ? `+${m.toLocaleString()}만` : `${m.toLocaleString()}만`;
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', overflow: 'visible' }}>
      {/* 그리드 */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={PAD.left} y1={t.y} x2={PAD.left + cW} y2={t.y}
                stroke="#e2e8f0" strokeWidth="1" />
          <text x={PAD.left - 8} y={t.y + 4} textAnchor="end" fontSize="10" fill="#a0aec0">
            {fmt(t.v)}
          </text>
        </g>
      ))}

      {/* 0원 선 */}
      {minV < 0 && maxV > 0 && (
        <line x1={PAD.left} y1={zeroY} x2={PAD.left + cW} y2={zeroY}
              stroke="#a0aec0" strokeWidth="1.2" strokeDasharray="5,3" />
      )}

      {/* 회수 시점 수직선 */}
      {pbX && (
        <>
          <line x1={pbX} y1={PAD.top} x2={pbX} y2={PAD.top + cH}
                stroke="#38a169" strokeWidth="1.5" strokeDasharray="5,3" />
          <text x={pbX + 5} y={PAD.top + 14} fontSize="10" fill="#38a169" fontWeight="700">
            {paybackYear}년 회수
          </text>
        </>
      )}

      {/* 꺾은선 */}
      <polyline points={pts} fill="none" stroke="#1E6FD9" strokeWidth="2.5"
                strokeLinejoin="round" strokeLinecap="round" />

      {/* 점 */}
      {vals.map((v, y) => (
        <circle key={y} cx={toX(y)} cy={toY(v)} r={y % 5 === 0 ? 4 : 2.5}
                fill={v >= 0 ? '#38a169' : '#e53e3e'} stroke="white" strokeWidth="1.2" />
      ))}

      {/* X축 레이블 */}
      {[0, 5, 10, 15, 20].map(y => (
        <text key={y} x={toX(y)} y={H - 8} textAnchor="middle" fontSize="11" fill="#718096">
          {y}년
        </text>
      ))}

      {/* X축 선 */}
      <line x1={PAD.left} y1={PAD.top + cH} x2={PAD.left + cW} y2={PAD.top + cH}
            stroke="#e2e8f0" strokeWidth="1.5" />
    </svg>
  );
}

// ── 투자 회수 시점 시각화 ─────────────────────────────────────────────────────
function PaybackViz({ paybackYear, installCost, yearlyRevenue, netProfit20y }) {
  const pct = Math.min(((paybackYear || 0) / 20) * 100, 100);
  const fmt만 = v => v ? `${Math.round(v / 10000).toLocaleString()}만원` : '-';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* 타임라인 바 */}
      <div>
        <div style={{ position: 'relative', height: 36, borderRadius: 18,
                      background: '#c6f6d5', overflow: 'visible' }}>
          {/* 투자 구간 */}
          <div style={{
            position: 'absolute', left: 0, top: 0, bottom: 0,
            width: `${pct}%`, minWidth: pct > 0 ? 4 : 0,
            background: 'linear-gradient(90deg, #fc8181, #f6ad55)',
            borderRadius: pct >= 100 ? 18 : '18px 0 0 18px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'white', fontSize: 11, fontWeight: 700,
          }}>
            {pct > 20 && `투자 회수 중 (${paybackYear}년)`}
          </div>
          {/* 회수 마커 */}
          {paybackYear && pct < 100 && (
            <div style={{
              position: 'absolute', top: -6, bottom: -6,
              left: `${pct}%`, width: 3,
              background: '#1E6FD9', transform: 'translateX(-50%)',
              borderRadius: 2,
            }} />
          )}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between',
                      fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
          <span>0년 투자 시작</span>
          {paybackYear && <span style={{ color: '#1E6FD9', fontWeight: 700 }}>↑ {paybackYear}년 투자 회수</span>}
          <span>20년 종료</span>
        </div>
      </div>

      {/* 요약 카드 2개 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ textAlign: 'center', padding: '14px 8px',
                      background: '#fff5f5', borderRadius: 10, border: '1px solid #fed7d7' }}>
          <div style={{ fontSize: 11, color: '#e53e3e', marginBottom: 4, fontWeight: 600 }}>
            💸 총 투자비
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#e53e3e' }}>
            {fmt만(installCost)}
          </div>
        </div>
        <div style={{ textAlign: 'center', padding: '14px 8px',
                      background: '#f0fff4', borderRadius: 10, border: '1px solid #c6f6d5' }}>
          <div style={{ fontSize: 11, color: '#38a169', marginBottom: 4, fontWeight: 600 }}>
            🏆 20년 순수익
          </div>
          <div style={{ fontSize: 20, fontWeight: 800, color: '#38a169' }}>
            {fmt만(netProfit20y)}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 섹션 헤더 헬퍼 ───────────────────────────────────────────────────────────
function SectionHeader({ title, badge, right }) {
  return (
    <div className="section-header">
      <div className="section-title-dot" />
      <span className="section-title">{title}</span>
      {badge && (
        <div className="badge badge-green" style={{ marginLeft: 8 }}>
          <span className="badge-dot" />{badge}
        </div>
      )}
      {right && <div style={{ marginLeft: 'auto' }}>{right}</div>}
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function ResultTabs({ result, markerPos, buildingPolygon, onMapClick, onReset }) {
  const [activeTab, setActiveTab]   = useState('location');
  const [layoutTab, setLayoutTab]   = useState('2d');
  const [aiState,   setAiState]     = useState('idle');   // idle|loading|done|error
  const [aiText,    setAiText]      = useState('');

  if (!result) return null;

  const {
    building = {}, system = {}, financial = {},
    monthly_data = [], panel_layout = null,
    report_url, pdf_url,
  } = result;

  const fmt만 = v => v ? `${Math.round(v / 10000).toLocaleString()}만원` : '-';

  // ── KPI 세트 ────────────────────────────────────────────────────────────────
  const locationKpis = [
    { icon: '⚡', label: '설치 용량',  value: system.totalKw ?? '-',                                unit: 'kW',  color: 'blue'   },
    { icon: '☀️', label: '연간 발전량', value: system.yearlyTotal ? system.yearlyTotal.toLocaleString() : '-', unit: 'kWh', color: 'orange' },
    { icon: '💰', label: '연간 수익',   value: financial.yearlyRevenue ? `${Math.round(financial.yearlyRevenue / 10000).toLocaleString()}만` : '-', unit: '원', color: 'green' },
    { icon: '📈', label: '투자 회수',   value: financial.paybackYear ?? '-',                          unit: '년',  color: 'blue'   },
  ];

  const revenueKpis = [
    { icon: '🏗️', label: '총 설치비용',    value: fmt만(financial.installCost),   unit: '', color: 'blue'   },
    { icon: '💵', label: '연간 전기 수익',  value: fmt만(financial.yearlyRevenue), unit: '', color: 'green'  },
    { icon: '📜', label: 'REC 수익(추정)', value: fmt만(financial.recRevenue),    unit: '', color: 'orange' },
    { icon: '🏆', label: '20년 순수익',    value: fmt만(financial.netProfit20y),  unit: '', color: 'green'  },
  ];

  // ── AI 평가 생성 ─────────────────────────────────────────────────────────────
  const generateAi = async () => {
    setAiState('loading');
    try {
      const res = await fetch('/api/ai-evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: building.address, building, system, financial }),
      });
      if (!res.ok) throw new Error('not_ready');
      const data = await res.json();
      setAiText(data.evaluation || '평가 결과를 받지 못했습니다.');
      setAiState('done');
    } catch {
      setAiText(
        '⚠️ AI 평가 기능은 다음 단계에서 Claude API와 연동될 예정입니다.\n\n' +
        `분석 주소: ${building.address || '-'}\n` +
        `설치 용량: ${system.totalKw}kW  |  연간 발전량: ${system.yearlyTotal?.toLocaleString()}kWh\n` +
        `투자 회수: ${financial.paybackYear}년  |  20년 순수익: ${fmt만(financial.netProfit20y)}`
      );
      setAiState('done');
    }
  };

  // ── 렌더링 ──────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* 성공 배너 */}
      <div className="alert-box alert-success" style={{ marginBottom: 16 }}>
        ✅ 분석이 완료되었습니다.
        <button className="btn btn-sm btn-outline" style={{ marginLeft: 'auto', flexShrink: 0 }}
          onClick={onReset}>새 분석</button>
      </div>

      {/* ── 탭 바 ─────────────────────────────────────────────────────────── */}
      <div className="result-tab-bar">
        {TABS.map(tab => (
          <button key={tab.id} className={`result-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}>
            <span className="result-tab-icon">{tab.icon}</span>
            <span className="result-tab-label">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── 탭 콘텐츠 ────────────────────────────────────────────────────── */}
      <div key={activeTab} className="result-tab-panel">

        {/* ════ 탭 1: 입지 분석 ════ */}
        {activeTab === 'location' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* KPI 카드 */}
            <div className="kpi-grid">
              {locationKpis.map((k, i) => <KpiCard key={i} {...k} />)}
            </div>

            {/* 위성지도 + 패널 오버레이 */}
            <div className="card card-accent">
              <SectionHeader
                title="🛰 위성지도 패널 오버레이"
                right={<span style={{ fontSize: 12, color: 'var(--text-muted)' }}>지도 클릭 → 새 위치 분석</span>}
              />
              <div style={{ padding: '0 0 4px' }}>
                <KakaoMap
                  markerPos={markerPos}
                  onMapClick={onMapClick}
                  buildingPolygon={buildingPolygon}
                  panelLayout={panel_layout}
                  height={320}
                />
              </div>
            </div>

            {/* 월별 발전량 */}
            <div className="card card-accent">
              <SectionHeader title="📊 월별 예상 발전량" badge="분석 완료" />
              <MonthlyChart data={monthly_data} />
            </div>

            {/* 태양 고도각 */}
            <div className="card card-accent">
              <SectionHeader title="☀️ 월별 태양 고도각" />
              <SolarAltitudeChart data={monthly_data} />
            </div>
          </div>
        )}

        {/* ════ 탭 2: 수익 분석 ════ */}
        {activeTab === 'revenue' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* 재무 KPI */}
            <div className="kpi-grid">
              {revenueKpis.map((k, i) => <KpiCard key={i} {...k} />)}
            </div>

            {/* 20년 누적 수익 차트 */}
            <div className="card card-accent">
              <SectionHeader title="📈 20년 누적 수익 예측" />
              <div className="chart-wrapper">
                <div className="chart-legend">
                  <div className="legend-item">
                    <div className="legend-dot" style={{ background: '#1E6FD9', borderRadius: '50%' }} />
                    누적 수익 (만원)
                  </div>
                  <div className="legend-item">
                    <div className="legend-dot" style={{ background: '#38a169', borderRadius: '50%' }} />
                    수익 구간
                  </div>
                  <div className="legend-item">
                    <div className="legend-dot" style={{ background: '#e53e3e', borderRadius: '50%' }} />
                    투자 회수 중
                  </div>
                </div>
                <CumulativeChart
                  installCost={financial.installCost || 0}
                  yearlyRevenue={financial.yearlyRevenue || 0}
                  paybackYear={financial.paybackYear}
                />
              </div>
            </div>

            {/* 투자 회수 시각화 */}
            <div className="card card-accent">
              <SectionHeader title="🎯 투자 회수 시점 분석" />
              <div style={{ padding: '12px 24px 20px' }}>
                <PaybackViz
                  paybackYear={financial.paybackYear}
                  installCost={financial.installCost}
                  yearlyRevenue={financial.yearlyRevenue}
                  netProfit20y={financial.netProfit20y}
                />
              </div>
            </div>

            {/* 재무 상세 */}
            <div className="card card-accent">
              <SectionHeader title="💸 재무 상세" />
              <div style={{ padding: '0 24px 16px' }}>
                {[
                  { label: '총 설치비용',      value: fmt만(financial.installCost) },
                  { label: '연간 전기 판매 수익', value: fmt만(financial.yearlyRevenue), cls: 'orange' },
                  { label: 'REC 수익 (추정)',   value: fmt만(financial.recRevenue),    cls: 'orange' },
                  { label: '투자 회수 기간',     value: financial.paybackYear ? `${financial.paybackYear}년` : '-', cls: 'blue' },
                  { label: '20년 순수익 (추정)', value: fmt만(financial.netProfit20y), cls: 'blue' },
                ].map((row, i) => (
                  <div className="info-row" key={i}>
                    <span className="info-row-label">{row.label}</span>
                    <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ════ 탭 3: 설계 분석 ════ */}
        {activeTab === 'design' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* 2D / 3D 패널 배치도 */}
            {panel_layout && (
              <div className="card card-accent">
                <SectionHeader
                  title="🔲 태양광 패널 가상 배치도"
                  right={
                    <div style={{ display: 'flex', gap: 6 }}>
                      {[{ id: '2d', label: '📐 2D' }, { id: '3d', label: '🧊 3D' }].map(({ id, label }) => (
                        <button key={id} onClick={() => setLayoutTab(id)} style={{
                          padding: '4px 12px', borderRadius: 7, border: 'none', cursor: 'pointer',
                          fontWeight: 600, fontSize: 12, transition: 'all 0.15s',
                          background: layoutTab === id ? 'var(--blue)' : 'var(--bg)',
                          color:      layoutTab === id ? 'white' : 'var(--text-secondary)',
                        }}>{label}</button>
                      ))}
                      <div className="badge badge-blue" style={{ marginLeft: 4 }}>
                        640W × {panel_layout.stats?.active_panels ?? '-'}매
                      </div>
                    </div>
                  }
                />
                <div style={{ padding: '0 4px 4px' }}>
                  {layoutTab === '2d' ? (
                    <PanelLayoutViewer layout={panel_layout} lat={result.lat} />
                  ) : (
                    <Suspense fallback={
                      <div style={{ height: 460, display: 'flex', alignItems: 'center',
                                    justifyContent: 'center', color: 'var(--text-muted)', fontSize: 14 }}>
                        <span className="spinner" style={{ marginRight: 8 }} />3D 뷰어 로딩 중...
                      </div>
                    }>
                      <PanelLayout3D layout={panel_layout} building={building} lat={result.lat} />
                    </Suspense>
                  )}
                </div>
              </div>
            )}

            {/* 건물 정보 + 배치 상세 */}
            <div className="result-main-grid">
              <BuildingInfo building={building} system={system} />

              <div className="card card-accent">
                <SectionHeader title="📐 배치 상세" />
                <div style={{ padding: '0 24px 16px' }}>
                  {[
                    { label: '총 패널 수',       value: panel_layout?.stats?.total_panels ?? '-' },
                    { label: '활성 패널',         value: panel_layout?.stats?.active_panels ?? '-',  cls: 'blue' },
                    { label: '패널 방위각',        value: panel_layout?.stats?.azimuth_deg != null ? `${panel_layout.stats.azimuth_deg}°` : '-' },
                    { label: '경사각(tilt)',       value: panel_layout?.stats?.tilt_deg != null ? `${panel_layout.stats.tilt_deg}°` : '-' },
                    { label: '행 × 열',           value: `${panel_layout?.stats?.row_count ?? '-'} × ${panel_layout?.stats?.col_count ?? '-'}` },
                    { label: '행 이격거리',        value: panel_layout?.stats?.row_spacing_m ? `${panel_layout.stats.row_spacing_m}m` : '-' },
                    { label: '지붕 형상',          value: panel_layout?.stats?.roof_shape ?? '-' },
                  ].map((row, i) => (
                    <div className="info-row" key={i}>
                      <span className="info-row-label">{row.label}</span>
                      <span className={`info-row-value ${row.cls || ''}`}>{String(row.value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* 다운로드 */}
            <div className="card">
              <DownloadButtons reportUrl={report_url} pdfUrl={pdf_url} />
            </div>
          </div>
        )}

        {/* ════ 탭 4: AI 종합 평가 ════ */}
        {activeTab === 'ai' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card card-accent">
              <SectionHeader
                title="🤖 Claude AI 종합 평가"
                right={<span className="badge badge-blue">Claude 3.5 Sonnet</span>}
              />
              <div style={{ padding: '16px 24px 20px' }}>
                {/* 분석 컨텍스트 요약 */}
                <div style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '14px 16px', marginBottom: 18,
                  fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7,
                }}>
                  <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)', fontSize: 13 }}>
                    📋 분석 컨텍스트
                  </div>
                  <div>📍 <strong>{building.address || '-'}</strong></div>
                  <div>⚡ 설치용량 <strong>{system.totalKw}kW</strong> · 연간 발전량 <strong>{system.yearlyTotal?.toLocaleString()}kWh</strong></div>
                  <div>💰 투자비 <strong>{fmt만(financial.installCost)}</strong> · 회수 <strong>{financial.paybackYear}년</strong> · 20년 순수익 <strong>{fmt만(financial.netProfit20y)}</strong></div>
                </div>

                {aiState === 'idle' && (
                  <button className="btn btn-primary"
                    style={{ width: '100%', padding: '13px', fontSize: 15, fontWeight: 700, borderRadius: 10 }}
                    onClick={generateAi}>
                    🤖 Claude AI로 종합 평가 생성
                  </button>
                )}

                {aiState === 'loading' && (
                  <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                    <div style={{ marginBottom: 14 }}>
                      <span className="spinner" style={{ width: 28, height: 28 }} />
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600 }}>Claude AI가 분석 중입니다…</div>
                    <div style={{ fontSize: 12, marginTop: 4 }}>입지 조건, 재무 지표, 설계 데이터를 종합 평가합니다</div>
                  </div>
                )}

                {(aiState === 'done' || aiState === 'error') && aiText && (
                  <div>
                    <div style={{
                      background: 'white', border: '1px solid var(--border)', borderRadius: 10,
                      padding: '20px 22px', fontSize: 14, lineHeight: 1.8,
                      color: 'var(--text-primary)', whiteSpace: 'pre-wrap',
                    }}>
                      {aiText}
                    </div>
                    <button className="btn btn-outline"
                      style={{ marginTop: 12, fontSize: 12 }}
                      onClick={() => { setAiState('idle'); setAiText(''); }}>
                      ↺ 다시 생성
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

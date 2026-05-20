import { useState, useEffect, useRef } from 'react';
import MonthlyChart from './MonthlyChart';
import SolarAltitudeChart from './SolarAltitudeChart';
import BuildingInfo from './BuildingInfo';
import DownloadButtons from './DownloadButtons';
import { HTTP_BASE } from '../lib/api';

export const TABS = [
  { id: 'location',   icon: 'fa-solid fa-location-dot',    label: '입지' },
  { id: 'revenue',    icon: 'fa-solid fa-chart-line',       label: '수익' },
  { id: 'design',     icon: 'fa-solid fa-drafting-compass', label: '설계' },
  { id: 'regulation', icon: 'fa-solid fa-scale-balanced',   label: '규제' },
  { id: 'ai',         icon: 'fa-solid fa-robot',            label: 'AI' },
  { id: 'report',     icon: 'fa-solid fa-file-lines',       label: '보고서' },
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

// ── AI 응답 마크다운 렌더러 ──────────────────────────────────────────────────
function AiMarkdown({ text }) {
  if (!text) return null;

  const parseLine = (line) => {
    // **bold** 인라인 처리
    const parts = line.split(/\*\*(.*?)\*\*/);
    if (parts.length === 1) return line;
    return parts.map((p, i) =>
      i % 2 === 1 ? <strong key={i}>{p}</strong> : p
    );
  };

  return (
    <div style={{ fontSize: 14, lineHeight: 1.85, color: 'var(--text-primary)' }}>
      {text.split('\n').map((line, i) => {
        if (line.startsWith('## ')) {
          return (
            <div key={i} style={{
              fontWeight: 700, fontSize: 15, color: 'var(--blue)',
              marginTop: i > 0 ? 22 : 0, marginBottom: 10,
              paddingBottom: 5, borderBottom: '1px solid var(--border)',
            }}>
              {line.slice(3)}
            </div>
          );
        }
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 5, paddingLeft: 4 }}>
              <span style={{ color: 'var(--blue)', flexShrink: 0, marginTop: 1 }}>•</span>
              <span>{parseLine(line.slice(2))}</span>
            </div>
          );
        }
        if (line === '') return <div key={i} style={{ height: 6 }} />;
        return (
          <div key={i} style={{ marginBottom: 3 }}>{parseLine(line)}</div>
        );
      })}
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

// ── 2D 모듈 배치도 ────────────────────────────────────────────────────────────
function PanelLayout2D({ panelLayout }) {
  const rows         = panelLayout?.stats?.row_count    || 3;
  const cols         = panelLayout?.stats?.col_count    || 4;
  const activePanels = panelLayout?.stats?.active_panels ?? rows * cols;
  const azimuth      = panelLayout?.stats?.azimuth_deg ?? 180;

  // 패널 크기 (60% 축소: max 18)
  const MAX_W = 180, MAX_H = 130;
  const GAP_R = 0.18;
  const ASPECT = 22 / 34;

  const colUnits = cols + (cols - 1) * GAP_R;
  const rowUnits = rows + (rows - 1) * GAP_R;
  const pwByW    = MAX_W / colUnits;
  const pwByH    = (MAX_H / rowUnits) * ASPECT;
  const PW       = Math.max(3, Math.min(pwByW, pwByH, 18));
  const PH       = PW / ASPECT;
  const GX       = PW * GAP_R;
  const GY       = PH * GAP_R;

  const gridW = cols * PW + (cols - 1) * GX;
  const gridH = rows * PH + (rows - 1) * GY;

  // 이중 테두리 여백
  const OUTER_PAD = 10;
  const INNER_PAD = 18;
  const TOTAL_PAD = OUTER_PAD + INNER_PAD;

  const drawW  = gridW + TOTAL_PAD * 2;
  const drawH  = gridH + TOTAL_PAD * 2;
  const LABEL_H = 20;

  // 나침반 (도면 아래 중앙)
  const CR     = 26;
  const CX     = drawW / 2;
  const DRAW_Y = LABEL_H;
  const CY     = DRAW_Y + drawH + 16 + CR;   // 도면 하단 16px 간격 후 중심

  const SVG_W  = drawW;
  const SVG_H  = CY + CR + 16;               // 나침반 하단 + 방위각 텍스트

  // 남향 화살표
  const sRad = ((azimuth - 90) * Math.PI) / 180;
  const sLen = CR - 7;
  const sx   = CX + sLen * Math.cos(sRad);
  const sy   = CY + sLen * Math.sin(sRad);

  // 배경 그리드 라인
  const GRID_STEP = 14;
  const gridLines = [];
  for (let gx = GRID_STEP; gx < drawW; gx += GRID_STEP) {
    gridLines.push(
      <line key={`gx${gx}`} x1={gx} y1={DRAW_Y} x2={gx} y2={DRAW_Y + drawH}
            stroke="rgba(255,255,255,0.07)" strokeWidth={0.5} strokeDasharray="2,4" />
    );
  }
  for (let gy = GRID_STEP; gy < drawH; gy += GRID_STEP) {
    gridLines.push(
      <line key={`gy${gy}`} x1={0} y1={DRAW_Y + gy} x2={drawW} y2={DRAW_Y + gy}
            stroke="rgba(255,255,255,0.07)" strokeWidth={0.5} strokeDasharray="2,4" />
    );
  }

  // 패널 렌더링
  const panels = [];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const n      = r * cols + c + 1;
      const active = n <= activePanels;
      const x      = TOTAL_PAD + c * (PW + GX);
      const y      = DRAW_Y + TOTAL_PAD + r * (PH + GY);
      panels.push(
        <g key={`p${r}-${c}`}>
          <rect x={x} y={y} width={PW} height={PH} rx={1}
                fill={active ? 'rgba(0,191,255,0.18)' : 'rgba(255,255,255,0.04)'}
                stroke={active ? '#00BFFF' : 'rgba(0,191,255,0.25)'}
                strokeWidth={active ? 0.8 : 0.5} />
          {active && PW >= 9 && <>
            <line x1={x+PW*.33} y1={y+1} x2={x+PW*.33} y2={y+PH-1} stroke="rgba(0,191,255,0.45)" strokeWidth={0.4}/>
            <line x1={x+PW*.67} y1={y+1} x2={x+PW*.67} y2={y+PH-1} stroke="rgba(0,191,255,0.45)" strokeWidth={0.4}/>
            <line x1={x+1} y1={y+PH*.5} x2={x+PW-1}   y2={y+PH*.5} stroke="rgba(0,191,255,0.45)" strokeWidth={0.4}/>
          </>}
        </g>
      );
    }
  }

  return (
    <div style={{ maxWidth: 500, margin: '0 auto' }}>
      <svg viewBox={`0 0 ${SVG_W} ${SVG_H}`} style={{ width: '100%', height: 'auto' }}>
        <defs>
          <marker id="arrowBP" markerWidth={7} markerHeight={7} refX={5} refY={3.5} orient="auto">
            <polygon points="0,0 7,3.5 0,7" fill="#00BFFF" />
          </marker>
        </defs>

        {/* 도면 배경 */}
        <rect x={0} y={DRAW_Y} width={drawW} height={drawH} fill="#0A1628" />
        {gridLines}

        {/* 외부 테두리 */}
        <rect x={0} y={DRAW_Y} width={drawW} height={drawH}
              fill="none" stroke="rgba(0,191,255,0.65)" strokeWidth={1.2} />
        {/* 내부 테두리 (이중) */}
        <rect x={OUTER_PAD} y={DRAW_Y + OUTER_PAD}
              width={drawW - OUTER_PAD * 2} height={drawH - OUTER_PAD * 2}
              fill="none" stroke="rgba(0,191,255,0.28)" strokeWidth={0.6} />

        {/* 상단 라벨바 */}
        <rect x={0} y={0} width={drawW} height={LABEL_H} fill="rgba(0,191,255,0.12)" />
        <rect x={0} y={0} width={drawW} height={LABEL_H}
              fill="none" stroke="rgba(0,191,255,0.65)" strokeWidth={1.2} />
        <text x={8} y={LABEL_H - 6} fontSize={8} fill="#00BFFF"
              fontFamily="monospace" letterSpacing={1.2}>배치 평면도</text>
        <text x={drawW - 8} y={LABEL_H - 6} fontSize={7.5}
              fill="rgba(0,191,255,0.7)" textAnchor="end" fontFamily="monospace">
          {cols}×{rows} ARRAY
        </text>

        {/* 패널 */}
        {panels}

        {/* 패널 수 레이블 (도면 하단 ~ 나침반 위 중간) */}
        <text x={drawW / 2} y={DRAW_Y + drawH + 11}
              textAnchor="middle" fontSize={8.5}
              fill="rgba(0,191,255,0.75)" fontFamily="monospace">
          ACTIVE {activePanels} / TOTAL {rows * cols} PNL
        </text>

        {/* 나침반 (도면 아래 중앙) */}
        <circle cx={CX} cy={CY} r={CR}     fill="#0A1628" stroke="rgba(0,191,255,0.65)" strokeWidth={1} />
        <circle cx={CX} cy={CY} r={CR - 5} fill="none"   stroke="rgba(0,191,255,0.2)"  strokeWidth={0.5} />
        {/* 십자선 */}
        <line x1={CX} y1={CY-CR+12} x2={CX} y2={CY+CR-12}
              stroke="rgba(255,255,255,0.15)" strokeWidth={0.5} />
        <line x1={CX-CR+12} y1={CY} x2={CX+CR-12} y2={CY}
              stroke="rgba(255,255,255,0.15)" strokeWidth={0.5} />
        <text x={CX}      y={CY-CR+11} textAnchor="middle" fontSize={8} fontWeight="700" fill="white"                 fontFamily="monospace">N</text>
        <text x={CX}      y={CY+CR-3}  textAnchor="middle" fontSize={8} fontWeight="700" fill="#00BFFF"               fontFamily="monospace">S</text>
        <text x={CX+CR-4} y={CY+3}     textAnchor="end"    fontSize={6.5}                fill="rgba(255,255,255,0.4)" fontFamily="monospace">E</text>
        <text x={CX-CR+4} y={CY+3}     textAnchor="start"  fontSize={6.5}                fill="rgba(255,255,255,0.4)" fontFamily="monospace">W</text>
        {/* 남향 화살표 */}
        <line x1={CX} y1={CY} x2={sx} y2={sy}
              stroke="#00BFFF" strokeWidth={1.5} markerEnd="url(#arrowBP)" />
        {/* 방위각 */}
        <text x={CX} y={CY + CR + 13} textAnchor="middle" fontSize={8}
              fill="rgba(0,191,255,0.8)" fontFamily="monospace">
          {azimuth}°
        </text>
      </svg>
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────────────
export default function ResultTabs({ result, markerPos, buildingPolygon, onMapClick, onReset,
                                    activeTab: externalTab, onTabChange }) {
  const [internalTab, setInternalTab] = useState('location');
  const activeTab  = externalTab  ?? internalTab;
  const setActiveTab = onTabChange ?? setInternalTab;
  const [aiState,   setAiState]     = useState('idle');   // idle|loading|retrying|streaming|done|error
  const [aiText,    setAiText]      = useState('');
  const [aiRetry,   setAiRetry]     = useState(null);    // {attempt, total, delay}

  const [ordinance,        setOrdinance]        = useState(null);
  const [ordinanceLoading, setOrdinanceLoading] = useState(false);
  const ordinanceFetched = useRef(false);

  if (!result) return null;

  const {
    building = {}, system = {}, financial = {},
    monthly_data = [], panel_layout = null,
    report_url, pdf_url, regulation = null,
    solar_check = null,
  } = result;

  const fmt만 = v => v ? `${Math.round(v / 10000).toLocaleString()}만원` : '-';

  // ── KPI 세트 ────────────────────────────────────────────────────────────────
  const locationKpis = [
    { icon: <i className="fa-solid fa-bolt" style={{marginRight:0}}></i>,              label: '설치 용량',  value: system.totalKw ?? '-',                                unit: 'kW',  color: 'blue'   },
    { icon: <i className="fa-solid fa-sun" style={{marginRight:0}}></i>,               label: '연간 발전량', value: system.yearlyTotal ? system.yearlyTotal.toLocaleString() : '-', unit: 'kWh', color: 'orange' },
    { icon: <i className="fa-solid fa-coins" style={{marginRight:0}}></i>,             label: '연간 수익',   value: financial.yearlyRevenue ? `${Math.round(financial.yearlyRevenue / 10000).toLocaleString()}만` : '-', unit: '원', color: 'green' },
    { icon: <i className="fa-solid fa-clock-rotate-left" style={{marginRight:0}}></i>, label: '투자 회수',   value: financial.paybackYear ?? '-',                          unit: '년',  color: 'blue'   },
  ];

  const revenueKpis = [
    { icon: '🏗️', label: '총 설치비용',    value: fmt만(financial.installCost),   unit: '', color: 'blue'   },
    { icon: '💵', label: '연간 전기 수익',  value: fmt만(financial.yearlyRevenue), unit: '', color: 'green'  },
    { icon: '📜', label: 'REC 수익(추정)', value: financial.recRevenue ? fmt만(financial.recRevenue) : '-', unit: '', color: 'orange' },
    { icon: '🏆', label: '20년 순수익',    value: fmt만(financial.netProfit20y),  unit: '', color: 'green'  },
  ];

  // ── 지자체 조례 조회 (규제 탭 진입 시 1회) ───────────────────────────────────
  useEffect(() => {
    if (activeTab !== 'regulation' || ordinanceFetched.current) return;
    const parts = (building.address || '').split(' ');
    const sido = parts[0] || '';
    const sigungu = parts[1] || '';
    if (!sido) return;
    ordinanceFetched.current = true;
    setOrdinanceLoading(true);
    fetch(`/api/ordinance?sido=${encodeURIComponent(sido)}&sigungu=${encodeURIComponent(sigungu)}`)
      .then(r => r.json())
      .then(data => { setOrdinance(data); })
      .catch(() => { setOrdinance({ found: false, ordinances: [], summary: null }); })
      .finally(() => setOrdinanceLoading(false));
  }, [activeTab, building.address, HTTP_BASE]);

  // ── AI 평가 생성 (Gemini SSE 스트리밍, 429 재시도 포함) ─────────────────────
  const generateAi = async () => {
    setAiState('loading');
    setAiText('');
    setAiRetry(null);
    try {
      const res = await fetch(`${HTTP_BASE}/api/ai-evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: building.address,
          building,
          system,
          financial,
          monthly_data,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();  // 미완성 줄 보존

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (payload === '[DONE]') { setAiState('done'); return; }
          try {
            const parsed = JSON.parse(payload);

            if (parsed.error) {
              setAiText(parsed.error);
              setAiState('error');
              return;
            }
            if (parsed.retrying) {
              setAiRetry(JSON.parse(parsed.retrying));
              setAiState('retrying');
              continue;
            }
            if (parsed.text) {
              setAiRetry(null);
              setAiState('streaming');
              setAiText(prev => prev + parsed.text);
            }
          } catch { /* JSON 파싱 실패 무시 */ }
        }
      }
      setAiState('done');
    } catch (err) {
      setAiText(err.message || '알 수 없는 오류가 발생했습니다.');
      setAiState('error');
    }
  };

  // ── 렌더링 ──────────────────────────────────────────────────────────────────
  return (
    <div>
      {/* ── 탭 바 ─────────────────────────────────────────────────────────── */}
      <div className="result-tab-bar">
        {TABS.map(tab => (
          <button key={tab.id} className={`result-tab-btn ${activeTab === tab.id ? 'active' : ''}`}
            onClick={() => setActiveTab(tab.id)}>
            <i className={tab.icon}></i>
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* ── 기존 태양광 감지 배너 ─────────────────────────────────────────── */}
      {solar_check?.has_existing && (
        <div className="solar-existing-banner">
          <i className="fa-solid fa-triangle-exclamation"></i>
          <div>
            <strong>기존 태양광 설비 감지</strong>
            <p>반경 100m 내 {solar_check.nearby_count}개의 태양광 발전소가 이미 설치되어 있습니다.
              중복 설치 가능 여부 및 계통 연계 용량을 사전에 확인하세요.</p>
          </div>
        </div>
      )}

      {/* ── 탭 콘텐츠 ────────────────────────────────────────────────────── */}
      <div key={activeTab} className="result-tab-panel">

        {/* ════ 탭 1: 입지 분석 ════ */}
        {activeTab === 'location' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* KPI 카드 */}
            <div className="kpi-grid">
              {locationKpis.map((k, i) => <KpiCard key={i} {...k} />)}
            </div>

            {/* 입지 요약 */}
            <div className="card card-accent">
              <SectionHeader title="📋 입지 요약" />
              <div style={{ padding: '0 24px 16px' }}>
                {[
                  { label: '주소',
                    value: building.address || '-' },
                  { label: '방위각',
                    value: building.azimuth != null
                      ? `${building.azimuth}° ${building.azimuthSource === 'override' ? '(수동 설정)' : '(자동 계산)'}`
                      : '-',
                    cls: 'blue' },
                  { label: '건물 용도',
                    value: building.purpose || '-' },
                  { label: '건축면적',
                    value: building.archArea ? `${building.archArea.toLocaleString()} m²` : '-' },
                  { label: '연간 일사량',
                    value: building.irradiation ? `${building.irradiation} kWh/m²` : '-',
                    cls: 'orange' },
                  { label: '용도지역',
                    value: regulation?.zones?.length
                      ? regulation.zones.join(' · ')
                      : (regulation ? '데이터 없음' : '분석 중…') },
                  { label: '설치 가능성',
                    value: regulation?.zoneFeasibility || '-',
                    cls: regulation?.zoneFeasibility === '가능' ? 'green'
                       : regulation?.zoneFeasibility === '불가' ? 'red' : '' },
                ].map((row, i) => (
                  <div className="info-row" key={i}>
                    <span className="info-row-label">{row.label}</span>
                    <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
                  </div>
                ))}
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
                  { label: 'REC 수익 (추정)',   value: financial.recRevenue ? fmt만(financial.recRevenue) : '-', cls: 'orange' },
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
            {/* 건물 정보 + 시스템 구성 (BuildingInfo에 두 카드 포함) — 전체 너비 */}
            <BuildingInfo building={building} system={system} />

            {/* 2D 모듈 배치도 */}
            {panel_layout && (
              <div className="card card-accent">
                <SectionHeader title="🔲 2D 모듈 배치도" badge="자동 생성" />
                <div style={{ padding: '12px 24px 20px' }}>
                  <PanelLayout2D panelLayout={panel_layout} />
                </div>
              </div>
            )}

            {/* 배치 상세 — 전체 너비 카드 */}
            <div className="card card-accent">
              <SectionHeader title="📐 배치 상세" />
              <div style={{ padding: '0 24px 16px' }}>
                {[
                  { label: '총 패널 수',   value: panel_layout?.stats?.total_panels ?? '-' },
                  { label: '활성 패널',    value: panel_layout?.stats?.active_panels ?? '-', cls: 'blue' },
                  { label: '패널 방위각',  value: panel_layout?.stats?.azimuth_deg != null ? `${panel_layout.stats.azimuth_deg}°` : '-' },
                  { label: '경사각(tilt)', value: panel_layout?.stats?.tilt_deg != null ? `${panel_layout.stats.tilt_deg}°` : '-' },
                  { label: '행 × 열',     value: `${panel_layout?.stats?.row_count ?? '-'} × ${panel_layout?.stats?.col_count ?? '-'}` },
                  { label: '행 이격거리',  value: panel_layout?.stats?.row_spacing_m ? `${panel_layout.stats.row_spacing_m}m` : '-' },
                  { label: '지붕 형상',    value: panel_layout?.stats?.roof_shape ?? '-' },
                ].map((row, i) => (
                  <div className="info-row" key={i}>
                    <span className="info-row-label">{row.label}</span>
                    <span className={`info-row-value ${row.cls || ''}`}>{String(row.value)}</span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}

        {/* ════ 탭 4: 규제 분석 ════ */}
        {activeTab === 'regulation' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {!regulation ? (
              <div className="card card-accent">
                <div style={{ padding: '40px 24px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <div style={{ fontSize: 36, marginBottom: 12 }}>🏛️</div>
                  <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>
                    규제 정보를 불러오지 못했습니다
                  </div>
                  <div style={{ fontSize: 13 }}>PNU 정보가 없거나 API 조회에 실패했습니다.</div>
                </div>
              </div>
            ) : (() => {
              const reg = regulation;
              const riskColor = {
                '낮음':   { bg: '#f0fff4', border: '#c6f6d5', text: '#276749', badge: '#38a169' },
                '보통':   { bg: '#fffbeb', border: '#fde68a', text: '#744210', badge: '#d69e2e' },
                '높음':   { bg: '#fff5f5', border: '#fed7d7', text: '#742a2a', badge: '#e53e3e' },
                '확인불가': { bg: '#f7fafc', border: '#e2e8f0', text: '#4a5568', badge: '#718096' },
              }[reg.riskLevel] || { bg: '#f7fafc', border: '#e2e8f0', text: '#4a5568', badge: '#718096' };

              const feasColor = {
                '가능':   '#38a169',
                '조건부': '#d69e2e',
                '불가':   '#e53e3e',
                '확인불가': '#718096',
              }[reg.zoneFeasibility] || '#718096';

              return (
                <>
                  {/* 종합 리스크 */}
                  <div className="card card-accent">
                    <SectionHeader title="⚠️ 종합 리스크 평가" />
                    <div style={{ padding: '16px 24px 20px' }}>
                      <div style={{
                        background: riskColor.bg, border: `1px solid ${riskColor.border}`,
                        borderRadius: 10, padding: '16px 20px', marginBottom: 12,
                        display: 'flex', alignItems: 'center', gap: 14,
                      }}>
                        <div style={{
                          width: 52, height: 52, borderRadius: '50%',
                          background: riskColor.badge, flexShrink: 0,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          color: 'white', fontSize: 20,
                        }}>
                          {reg.riskLevel === '낮음' ? '✓' : reg.riskLevel === '높음' ? '✕' : '!'}
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: 18, color: riskColor.text }}>
                            리스크 {reg.riskLevel}
                          </div>
                          {reg.riskReasons.map((r, i) => (
                            <div key={i} style={{ fontSize: 13, color: riskColor.text, marginTop: 3, opacity: 0.85 }}>
                              {r}
                            </div>
                          ))}
                        </div>
                      </div>
                      {reg.errors.filter(e => !e.includes('토지특성')).length > 0 && (
                        <div style={{
                          background: '#fffbeb', border: '1px solid #fde68a',
                          borderRadius: 8, padding: '10px 14px', fontSize: 12, color: '#744210',
                        }}>
                          ⚠️ {reg.errors.filter(e => !e.includes('토지특성')).join(' · ')}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 용도지역 */}
                  <div className="card card-accent">
                    <SectionHeader title="🗺️ 용도지역 정보" />
                    <div style={{ padding: '0 24px 16px' }}>
                      {reg.zones.length > 0 ? (
                        <>
                          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, marginTop: 4 }}>
                            {reg.zones.map((z, i) => (
                              <span key={i} style={{
                                background: '#ebf4ff', color: '#2b6cb0',
                                border: '1px solid #bee3f8', borderRadius: 6,
                                fontSize: 13, fontWeight: 700, padding: '4px 12px',
                              }}>{z}</span>
                            ))}
                            <span style={{
                              background: feasColor + '22', color: feasColor,
                              border: `1px solid ${feasColor}44`,
                              borderRadius: 6, fontSize: 13, fontWeight: 700, padding: '4px 12px',
                            }}>설치 {reg.zoneFeasibility}</span>
                          </div>
                          {reg.zoneNote && (
                            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                              {reg.zoneNote}
                            </div>
                          )}
                        </>
                      ) : (
                        <div style={{ fontSize: 13, color: 'var(--text-muted)', paddingTop: 8 }}>
                          용도지역 정보 없음
                        </div>
                      )}
                    </div>
                  </div>

                  {/* 행위 제한 구역 */}
                  {reg.restrictions.length > 0 && (
                    <div className="card card-accent">
                      <SectionHeader title="🚫 행위 제한 구역" />
                      <div style={{ padding: '8px 24px 16px' }}>
                        {reg.restrictions.map((r, i) => (
                          <div key={i} className="info-row">
                            <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>• {r}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 개발행위허가 검토 */}
                  <div className="card card-accent">
                    <SectionHeader title="🏗️ 개발행위허가 검토" />
                    <div style={{ padding: '0 24px 16px' }}>
                      {/* 건축물 지붕 */}
                      <div style={{ marginBottom: 14 }}>
                        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 6 }}>
                          건축허가·신고 대상
                        </div>
                        {[
                          '건축물 지붕 태양광 설치 → 건축허가 또는 신고 대상',
                          reg.isFarmland ? '농지 설치 → 개발행위허가 필수 (농지법 적용)' : null,
                          reg.isForest   ? '임야 설치 → 개발행위허가 필수 (산지관리법 적용)' : null,
                          (!reg.isFarmland && !reg.isForest && reg.zoneFeasibility === '조건부')
                            ? '용도지역 조건부 허용 → 개발행위허가 필요' : null,
                        ].filter(Boolean).map((item, i) => (
                          <div key={i} className="info-row">
                            <span style={{ fontSize: 13, color: 'var(--text-primary)' }}>• {item}</span>
                          </div>
                        ))}
                      </div>
                      {/* 용도지역별 건폐율/용적률 */}
                      {reg.zones.length > 0 && (
                        <div style={{ marginBottom: 14 }}>
                          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 6 }}>
                            용도지역 제한
                          </div>
                          <div className="info-row">
                            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                              {reg.zoneNote || `${reg.zones[0]} 기준 건폐율·용적률 제한 확인 필요`}
                            </span>
                          </div>
                        </div>
                      )}
                      {/* 경관심의 / 환경영향평가 */}
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 6 }}>
                          규모별 추가 검토
                        </div>
                        {[
                          { cond: (system.totalKw ?? 0) >= 100,  label: `경관심의 대상 (100kW 이상 — 현재 ${system.totalKw}kW)`,   color: '#d69e2e' },
                          { cond: (system.totalKw ?? 0) >= 1000, label: `환경영향평가 대상 (1MW 이상 — 현재 ${system.totalKw}kW)`,  color: '#e53e3e' },
                          { cond: (system.totalKw ?? 0) < 100,   label: `경관심의 불필요 (100kW 미만 — 현재 ${system.totalKw}kW)`,  color: '#38a169' },
                        ].filter(i => i.cond).map((item, i) => (
                          <div key={i} className="info-row">
                            <span style={{ fontSize: 13, color: item.color, fontWeight: 600 }}>• {item.label}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* 농지/산지 규제 */}
                  <div className="card card-accent">
                    <SectionHeader title="🌾 농지·산지 규제" />
                    <div style={{ padding: '0 24px 16px' }}>
                      {!reg.isFarmland && !reg.isForest ? (
                        <div className="info-row">
                          <span style={{ fontSize: 13, color: '#38a169', fontWeight: 600 }}>
                            ✓ 농지·산지 해당 없음 — 추가 전용허가 불필요
                          </span>
                        </div>
                      ) : (
                        <>
                          {reg.isFarmland && [
                            '농지전용허가 필요 (농림축산식품부)',
                            '농업진흥구역 해당 여부 별도 확인 필수',
                            '농업진흥구역 내 태양광 설치 원칙적 불허',
                          ].map((item, i) => (
                            <div key={`f${i}`} className="info-row">
                              <span style={{ fontSize: 13, color: '#c05621' }}>• {item}</span>
                            </div>
                          ))}
                          {reg.isForest && [
                            '산지전용허가 필요 (산림청)',
                            '보전산지(공익용·임업용) 설치 불허',
                            '준보전산지는 조건부 허용 가능',
                          ].map((item, i) => (
                            <div key={`w${i}`} className="info-row">
                              <span style={{ fontSize: 13, color: '#744210' }}>• {item}</span>
                            </div>
                          ))}
                        </>
                      )}
                    </div>
                  </div>

                  {/* 전력계통 연계 판단 */}
                  <div className="card card-accent">
                    <SectionHeader title="🔌 전력계통 연계 판단" />
                    <div style={{ padding: '0 24px 16px' }}>
                      {(() => {
                        const kw = system.totalKw ?? 0;
                        const isLow  = kw < 100;
                        const needBiz = kw > 1000;
                        return (
                          <>
                            <div className="info-row">
                              <span className="info-row-label">연계 방식</span>
                              <span className="info-row-value" style={{
                                fontWeight: 700,
                                color: isLow ? '#2b6cb0' : '#c05621',
                              }}>
                                {isLow ? `저압 연계 (100kW 미만 — ${kw}kW)` : `고압 연계 (100kW 이상 — ${kw}kW)`}
                              </span>
                            </div>
                            <div className="info-row">
                              <span className="info-row-label">한전 계통 연계 신청</span>
                              <span className="info-row-value" style={{ fontSize: 13 }}>필수 (한전 사이버지점 신청)</span>
                            </div>
                            <div className="info-row">
                              <span className="info-row-label">발전사업허가</span>
                              <span className="info-row-value" style={{
                                fontWeight: 700,
                                color: needBiz ? '#e53e3e' : '#38a169',
                              }}>
                                {needBiz
                                  ? `필요 (1,000kW 초과 — ${kw}kW)`
                                  : `불필요 (1,000kW 이하 — ${kw}kW)`}
                              </span>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>

                  {/* 지자체 조례 */}
                  <div className="card card-accent">
                    <SectionHeader title="📜 지자체 조례 조회" />
                    <div style={{ padding: '8px 24px 20px' }}>
                      {ordinanceLoading ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
                          <div style={{
                            width: 18, height: 18, border: '2px solid var(--border)',
                            borderTopColor: 'var(--blue)', borderRadius: '50%',
                            animation: 'spin 0.8s linear infinite', flexShrink: 0,
                          }} />
                          조례 정보를 조회 중입니다…
                        </div>
                      ) : ordinance ? (
                        <>
                          {ordinance.found ? (
                            <>
                              <div style={{ marginBottom: 10 }}>
                                {(ordinance.ordinances || [])
                                  .filter(o => o.title && !/^\d+/.test(o.title.trim()))
                                  .map((o, i) => (
                                  <div key={i} style={{ fontSize: 13, color: 'var(--text-primary)', marginBottom: 4 }}>
                                    <a href={o.link} target="_blank" rel="noopener noreferrer"
                                       style={{ color: '#2b6cb0', textDecoration: 'underline' }}>
                                      {o.title}
                                    </a>
                                    {o.date && <span style={{ color: 'var(--text-muted)', marginLeft: 6 }}>{o.date}</span>}
                                    {o.note && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{o.note}</div>}
                                  </div>
                                ))}
                              </div>
                              {ordinance.summary && (
                                <div style={{
                                  background: '#ebf8ff', border: '1px solid #bee3f8',
                                  borderRadius: 8, padding: '12px 14px', fontSize: 13,
                                }}>
                                  <div style={{ fontWeight: 700, color: '#2b6cb0', marginBottom: 8 }}>AI 요약</div>
                                  {[
                                    { label: '제한 사항', value: ordinance.summary.restrictions },
                                    { label: '지원 내용', value: ordinance.summary.support },
                                    { label: '허가 절차', value: ordinance.summary.procedure },
                                  ].map((row, i) => row.value && (
                                    <div key={i} style={{ marginBottom: 6 }}>
                                      <span style={{ fontWeight: 600, color: '#2c5282' }}>{row.label}: </span>
                                      <span style={{ color: '#2d3748' }}>{row.value}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </>
                          ) : (
                            <>
                              <div style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 10 }}>
                                {(() => {
                                  const msg = ordinance.message || '';
                                  return /^\d+/.test(msg) ? '해당 지역 관련 조례를 찾지 못했습니다.' : (msg || '해당 지역 관련 조례를 찾지 못했습니다.');
                                })()}
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
                                {(() => {
                                  const sg = ordinance.sigungu && !/^\d+$/.test(ordinance.sigungu)
                                    ? ordinance.sigungu
                                    : ((building.address || '').split(' ')[1] || '');
                                  const links = [
                                    { label: '자치법규 정보시스템', href: 'https://www.elis.go.kr' },
                                    { label: '국가법령정보센터 태양광 조례 검색', href: 'https://www.law.go.kr/ordinSc.do?query=태양광' },
                                  ];
                                  if (sg && !/^\d+$/.test(sg)) {
                                    links.push({
                                      label: `${sg}청 홈페이지 검색`,
                                      href: `https://search.naver.com/search.naver?query=${encodeURIComponent(sg + '청 홈페이지')}`,
                                    });
                                  }
                                  return links.map((link, i) => (
                                    <a key={i} href={link.href} target="_blank" rel="noopener noreferrer"
                                       style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: '#2b6cb0', textDecoration: 'underline' }}>
                                      <i className="fa-solid fa-arrow-up-right-from-square" style={{ fontSize: 10 }}></i>
                                      {link.label}
                                    </a>
                                  ));
                                })()}
                              </div>
                            </>
                          )}
                        </>
                      ) : (
                        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>조례 조회 정보가 없습니다.</div>
                      )}
                    </div>
                  </div>

                  {/* 한전 계통연계 */}
                  <div className="card card-accent">
                    <SectionHeader title="⚡ 한전 계통연계 선로용량" />
                    <div style={{ padding: '16px 24px 20px' }}>
                      <div className="kepco-guide-card">
                        {/* 단계별 안내 */}
                        <div className="kepco-steps">
                          {[
                            '아래 버튼으로 한전 사이버지점 접속',
                            '주소 또는 전주번호 입력하여 조회',
                            `배전선로 잔여용량 확인 (설치용량 ${system.totalKw ?? '-'}kW 이상 필요)`,
                            '변전소/변압기/DL별 잔여용량이 설치용량 이상인지 확인',
                          ].map((text, i) => (
                            <div key={i} className="step">
                              <span className="step-num">{i + 1}</span>
                              <span>{text}</span>
                            </div>
                          ))}
                        </div>

                        {/* 확인 기준 */}
                        <div className="kepco-criteria">
                          {[
                            '변전소 여유용량 (vol1): 설치용량 이상',
                            '변압기 여유용량 (vol2): 설치용량 이상',
                            'DL 여유용량 (vol3): 설치용량 이상',
                          ].map((text, i) => (
                            <div key={i} className="criteria-item">
                              <i className="fa-solid fa-circle-check" style={{ color: 'var(--green)', marginRight: 6 }}></i>
                              <span>{text}</span>
                            </div>
                          ))}
                        </div>

                        {/* 바로가기 버튼 */}
                        <a
                          href={reg.kepcoUrl || 'https://cyber.kepco.co.kr/ckepco/front/main.do'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn-kepco-primary"
                        >
                          <i className="fa-solid fa-arrow-up-right-from-square"></i>
                          한전 선로용량 직접 조회
                        </a>
                      </div>

                      {/* 주의사항 */}
                      <div className="kepco-notice">
                        <i className="fa-solid fa-triangle-exclamation"></i>
                        현재 잔여용량이 있어도 타 사업자 허가 신청 현황 확인 필수
                      </div>
                    </div>
                  </div>
                </>
              );
            })()}
          </div>
        )}

        {/* ════ 탭 5: AI 종합 평가 ════ */}
        {activeTab === 'ai' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card card-accent">
              <SectionHeader
                title="🤖 AI 종합 평가"
                right={<span className="badge badge-blue">Gemini 1.5 Flash</span>}
              />
              <div style={{ padding: '16px 24px 20px' }}>

                {/* 분석 컨텍스트 요약 */}
                <div style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '14px 16px', marginBottom: 18,
                  fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8,
                }}>
                  <div style={{ fontWeight: 700, marginBottom: 6, color: 'var(--text-primary)' }}>
                    📋 분석 컨텍스트
                  </div>
                  <div>📍 {building.address || '-'}</div>
                  <div>⚡ 설치용량 <strong>{system.totalKw}kW</strong> · 연간 발전량 <strong>{system.yearlyTotal?.toLocaleString()}kWh</strong></div>
                  <div>💰 투자비 <strong>{fmt만(financial.installCost)}</strong> · 회수 <strong>{financial.paybackYear}년</strong> · 20년 순수익 <strong>{fmt만(financial.netProfit20y)}</strong></div>
                </div>

                {/* 초기: 버튼 */}
                {aiState === 'idle' && (
                  <button className="btn btn-primary"
                    style={{ width: '100%', padding: '14px', fontSize: 15, fontWeight: 700, borderRadius: 10 }}
                    onClick={generateAi}>
                    <i className="fa-solid fa-wand-magic-sparkles"></i> AI 종합 평가 생성
                  </button>
                )}

                {/* 분석 중 */}
                {(aiState === 'loading' || aiState === 'retrying') && (
                  <div style={{ textAlign: 'center', padding: '44px 0', color: 'var(--text-muted)' }}>
                    <span className="spinner" style={{ width: 28, height: 28, display: 'inline-block', marginBottom: 14 }} />
                    {aiState === 'retrying' && aiRetry ? (
                      <>
                        <div style={{ fontSize: 14, fontWeight: 600, color: '#b45309' }}>
                          AI 분석 중 일시적 오류가 발생했습니다. 잠시 후 자동으로 재시도합니다.
                        </div>
                        <div style={{ fontSize: 12, marginTop: 4 }}>
                          재시도 중 ({aiRetry.attempt}/{aiRetry.total})… {aiRetry.delay}초 대기
                        </div>
                      </>
                    ) : (
                      <>
                        <div style={{ fontSize: 14, fontWeight: 600 }}>AI가 분석 중입니다…</div>
                        <div style={{ fontSize: 12, marginTop: 4 }}>입지·재무·설계 데이터를 종합 평가합니다</div>
                      </>
                    )}
                  </div>
                )}

                {/* 스트리밍 / 완료 */}
                {(aiState === 'streaming' || aiState === 'done') && (
                  <div>
                    <div style={{
                      background: '#fafbfc', border: '1px solid var(--border)', borderRadius: 10,
                      padding: '20px 22px', minHeight: 120,
                    }}>
                      <AiMarkdown text={aiText} />
                      {aiState === 'streaming' && (
                        <span className="ai-cursor" />
                      )}
                    </div>
                    {aiState === 'done' && (
                      <button className="btn btn-outline"
                        style={{ marginTop: 12, fontSize: 12 }}
                        onClick={() => { setAiState('idle'); setAiText(''); setAiRetry(null); }}>
                        <i className="fa-solid fa-arrows-rotate"></i> 다시 생성
                      </button>
                    )}
                  </div>
                )}

                {/* 오류 */}
                {aiState === 'error' && (
                  <div>
                    <div style={{
                      background: '#fff5f5', border: '1px solid #fed7d7', borderRadius: 10,
                      padding: '20px 22px', color: '#c53030',
                    }}>
                      <div style={{ fontWeight: 700, marginBottom: 6 }}>
                        AI 분석 중 일시적 오류가 발생했습니다.
                      </div>
                      <div style={{ fontSize: 13 }}>
                        {aiText || '잠시 후 다시 시도해주세요.'}
                      </div>
                    </div>
                    <button className="btn btn-outline"
                      style={{ marginTop: 12, fontSize: 12 }}
                      onClick={() => { setAiState('idle'); setAiText(''); setAiRetry(null); }}>
                      <i className="fa-solid fa-arrows-rotate"></i> 다시 시도
                    </button>
                  </div>
                )}

              </div>
            </div>
          </div>
        )}

        {/* ════ 탭 6: 보고서 ════ */}
        {activeTab === 'report' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* 프로젝트 개요 */}
            <div className="card card-accent">
              <SectionHeader title="📋 프로젝트 개요" />
              <div style={{ padding: '0 24px 16px' }}>
                {[
                  { label: '분석 주소',   value: building.address || '-' },
                  { label: '분석일',      value: new Date().toLocaleDateString('ko-KR') },
                  { label: '건물 용도',   value: building.roofType || '-' },
                  { label: '지붕 형상',   value: building.roofShape || '-' },
                  { label: '층수',        value: building.floor ? `${building.floor}층` : '-' },
                  { label: '건축면적',    value: building.archArea ? `${building.archArea.toLocaleString()} m²` : '-' },
                ].map((row, i) => (
                  <div className="info-row" key={i}>
                    <span className="info-row-label">{row.label}</span>
                    <span className="info-row-value">{String(row.value)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 핵심 지표 요약 */}
            <div className="card card-accent">
              <SectionHeader title="⚡ 핵심 지표 요약" />
              <div style={{ padding: '0 24px 16px' }}>
                <div className="kpi-grid" style={{ marginBottom: 12 }}>
                  {[
                    { label: '설치 용량',  value: system.totalKw ?? '-',                                              unit: 'kW',  color: 'blue'   },
                    { label: '연간 발전량', value: system.yearlyTotal ? system.yearlyTotal.toLocaleString() : '-',      unit: 'kWh', color: 'orange' },
                    { label: '연간 수익',  value: financial.yearlyRevenue ? `${Math.round(financial.yearlyRevenue/10000).toLocaleString()}만` : '-', unit: '원', color: 'green' },
                    { label: '투자 회수',  value: financial.paybackYear ?? '-',                                        unit: '년',  color: 'blue'   },
                  ].map((k, i) => <KpiCard key={i} {...k} />)}
                </div>
                {[
                  { label: '총 설치비용',   value: financial.installCost   ? `${Math.round(financial.installCost/10000).toLocaleString()}만원`   : '-' },
                  { label: '20년 순수익',   value: financial.netProfit20y  ? `${Math.round(financial.netProfit20y/10000).toLocaleString()}만원`  : '-' },
                  { label: '패널 수',       value: system.panelCount ? `${system.panelCount}매 × 640W` : '-' },
                  { label: '인버터 용량',   value: system.inverterKw ? `${system.inverterKw} kW` : '-' },
                ].map((row, i) => (
                  <div className="info-row" key={i}>
                    <span className="info-row-label">{row.label}</span>
                    <span className="info-row-value blue">{row.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 설계 요약 */}
            <div className="card card-accent">
              <SectionHeader title="📐 설계 요약" />
              <div style={{ padding: '0 24px 16px' }}>
                {[
                  { label: '패널 방위각',  value: panel_layout?.stats?.azimuth_deg != null ? `${panel_layout.stats.azimuth_deg}°` : '-' },
                  { label: '경사각',       value: panel_layout?.stats?.tilt_deg != null    ? `${panel_layout.stats.tilt_deg}°`    : '-' },
                  { label: '행 × 열',     value: `${panel_layout?.stats?.row_count ?? '-'} × ${panel_layout?.stats?.col_count ?? '-'}` },
                  { label: '행 이격거리',  value: panel_layout?.stats?.row_spacing_m ? `${panel_layout.stats.row_spacing_m}m` : '-' },
                  { label: '지붕 형상',    value: panel_layout?.stats?.roof_shape ?? '-' },
                ].map((row, i) => (
                  <div className="info-row" key={i}>
                    <span className="info-row-label">{row.label}</span>
                    <span className="info-row-value">{String(row.value)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 규제 요약 */}
            {regulation && (
              <div className="card card-accent">
                <SectionHeader title="⚖️ 규제 검토 요약" />
                <div style={{ padding: '0 24px 16px' }}>
                  {[
                    { label: '리스크 등급',  value: regulation.riskLevel || '-',      cls: regulation.riskLevel === '낮음' ? 'green' : regulation.riskLevel === '높음' ? 'orange' : '' },
                    { label: '용도지역',     value: regulation.zones?.join(', ') || '-' },
                    { label: '입지 가능성',  value: regulation.zoneFeasibility || '-' },
                    { label: '지목',         value: (regulation.landCategory && regulation.landCategory !== '-') ? regulation.landCategory : '정보 없음' },
                  ].map((row, i) => (
                    <div className="info-row" key={i}>
                      <span className="info-row-label">{row.label}</span>
                      <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
                    </div>
                  ))}
                  {regulation.riskReasons?.length > 0 && (
                    <div style={{ marginTop: 8, padding: '8px 12px', background: 'var(--bg)', borderRadius: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
                      {regulation.riskReasons.join(' · ')}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* AI 평가 안내 */}
            <div className="card card-accent">
              <SectionHeader title="🤖 AI 종합 평가" />
              <div style={{ padding: '12px 24px 16px', fontSize: 13, color: 'var(--text-muted)' }}>
                <i className="fa-solid fa-circle-info" style={{ marginRight: 6, color: 'var(--blue)' }}></i>
                AI 탭에서 Gemini 기반 종합 평가를 확인하세요.
                <button
                  className="btn btn-sm btn-outline"
                  style={{ marginLeft: 12 }}
                  onClick={() => setActiveTab('ai')}
                >
                  AI 탭으로 이동
                </button>
              </div>
            </div>

            {/* 다운로드 / 인쇄 */}
            <div className="card card-accent">
              <SectionHeader title="📥 보고서 저장" />
              <div style={{ padding: '16px 24px 20px', display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
                {report_url && (
                  <a
                    href={`${HTTP_BASE}${report_url}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary"
                    style={{ textDecoration: 'none' }}
                  >
                    <i className="fa-solid fa-file-lines"></i> 웹 보고서 보기
                  </a>
                )}
                {pdf_url && (
                  <a
                    href={`${HTTP_BASE}${pdf_url}`}
                    download
                    className="btn btn-outline"
                    style={{ textDecoration: 'none', borderColor: 'var(--orange)', color: 'var(--orange)' }}
                  >
                    <i className="fa-solid fa-file-pdf"></i> PDF 다운로드
                  </a>
                )}
                <button
                  className="btn btn-outline"
                  onClick={() => window.print()}
                  style={{ marginLeft: 'auto' }}
                >
                  <i className="fa-solid fa-print"></i> 인쇄
                </button>
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}

import MonthlyChart from './MonthlyChart'
import DownloadButtons from './DownloadButtons'

const METRICS = [
  {
    key: 'capacity', label: '시스템 용량', unit: 'kWp',
    iconText: '⚡', iconColor: '#1E6FD9', iconBg: '#E8F2FF', lineColor: '#1E6FD9',
    highlight: true,
    get: s => s['태양광시스템']?.['총용량_kW'],
    fmt: v => v?.toFixed(1),
  },
  {
    key: 'generation', label: '연간 발전량', unit: 'kWh',
    iconText: '☀', iconColor: '#FF6B35', iconBg: '#FFF1EB', lineColor: '#FF6B35',
    get: s => s['태양광시스템']?.['연간발전량_kWh'],
    fmt: v => v?.toLocaleString(),
  },
  {
    key: 'cost', label: '예상 설치비', unit: '만원',
    iconText: '💳', iconColor: '#F59E0B', iconBg: '#FFFBEB', lineColor: '#F59E0B',
    get: s => s['경제성']?.['예상설치비_만원'],
    fmt: v => v?.toLocaleString(),
  },
  {
    key: 'payback', label: '투자 회수기간', unit: '년',
    iconText: '📈', iconColor: '#22C55E', iconBg: '#ECFDF5', lineColor: '#22C55E',
    get: s => s['경제성']?.['단순회수기간_년'],
    fmt: v => v?.toFixed(1),
  },
  {
    key: 'co2', label: 'CO₂ 저감량', unit: 'kg/년',
    iconText: '🌿', iconColor: '#10B981', iconBg: '#ECFDF5', lineColor: '#10B981',
    get: s => s['경제성']?.['연간CO2저감_kg'],
    fmt: v => v?.toLocaleString(),
  },
]

export default function ResultCards({ summary, htmlPath, pdfPath }) {
  if (!summary) return null

  const monthly    = summary['태양광시스템']?.['월별발전량_kWh']
  const notes      = summary['특이사항'] || []
  const address    = summary['주소']
  const isFallback = summary['건물정보']?.['추정값'] === true

  return (
    <div className="result-section">
      <div className="result-header-row">
        <div className="result-address-badge">
          <span className="result-addr-dot" />
          {address}
        </div>
        <span className="result-status-badge">분석 완료</span>
      </div>

      {isFallback && (
        <div className="fallback-banner">
          <span className="fallback-icon">⚠</span>
          <span>
            건축물대장 API 조회 실패 — 기본값(100㎡ 평지붕)으로 추정한 결과입니다.
            실제 건물과 수치가 다를 수 있습니다.
          </span>
        </div>
      )}

      <div className="kpi-grid">
        {METRICS.map((m, i) => {
          const raw     = m.get(summary)
          const display = raw != null ? m.fmt(raw) : '—'
          return (
            <div
              key={m.key}
              className={`kpi-card${m.highlight ? ' kpi-card--highlight' : ''}`}
              style={{ animationDelay: `${i * 0.07}s` }}
            >
              <div className="kpi-body">
                <div className="kpi-left">
                  <div className="kpi-val">{display}</div>
                  <div className="kpi-unit">{m.unit}</div>
                  <div className="kpi-lbl">{m.label}</div>
                </div>
                <div className="kpi-icon-box" style={{ background: m.iconBg }}>
                  <span className="kpi-icon-text" style={{ color: m.iconColor }}>{m.iconText}</span>
                </div>
              </div>
              <div className="kpi-line" style={{ background: m.lineColor }} />
            </div>
          )
        })}
      </div>

      <MonthlyChart values={monthly} />

      <div className="sol-card section-panel">
        <div className="sol-card-title">보고서 다운로드</div>
        <DownloadButtons htmlPath={htmlPath} pdfPath={pdfPath} />
      </div>

      {notes.length > 0 && (
        <div className="sol-card section-panel">
          <div className="sol-card-title">특이사항</div>
          <ul className="notes-list">
            {notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}

      <BuildingInfo summary={summary} />

      <p className="result-panel-note">태양광 모듈 용량은 640W 기준으로 산정하였습니다.</p>
    </div>
  )
}

function BuildingInfo({ summary }) {
  const b = summary['건물정보']
  if (!b) return null

  const rows = [
    ['건물 유형', b['유형']],
    ['층수',      b['층수']        ? `${b['층수']}층`        : null],
    ['지붕 면적', b['지붕면적_m2'] ? `${b['지붕면적_m2']} m²` : null],
    ['지붕 형태', b['지붕형태']],
    ['경사각',    b['경사각_deg']  ? `${b['경사각_deg']}°`   : null],
    ['구조',      b['구조']],
  ].filter(([, v]) => v)

  const sys = summary['태양광시스템']
  const sysRows = [
    ['패널 수',     sys?.['패널수']        ? `${sys['패널수']} 장`        : null],
    ['인버터 용량', sys?.['인버터용량_kW'] ? `${sys['인버터용량_kW']} kW` : null],
    ['직병렬 구성', sys?.['직병렬구성']],
  ].filter(([, v]) => v)

  return (
    <div className="info-grid">
      <InfoTable title="건물 정보"   rows={rows} />
      <InfoTable title="시스템 구성" rows={sysRows} />
    </div>
  )
}

function InfoTable({ title, rows }) {
  return (
    <div className="sol-card section-panel">
      <div className="sol-card-title">{title}</div>
      <table className="info-table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td>{k}</td>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

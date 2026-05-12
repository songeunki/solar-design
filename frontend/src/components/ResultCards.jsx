import MonthlyChart from './MonthlyChart'
import DownloadButtons from './DownloadButtons'

const METRICS = [
  {
    key: 'capacity',
    icon: '⚡',
    label: '시스템 용량',
    unit: 'kW',
    highlight: true,
    get: s => s['태양광시스템']?.['총용량_kW'],
    fmt: v => v?.toFixed(1),
  },
  {
    key: 'generation',
    icon: '🔆',
    label: '연간 발전량',
    unit: 'kWh/년',
    get: s => s['태양광시스템']?.['연간발전량_kWh'],
    fmt: v => v?.toLocaleString(),
  },
  {
    key: 'cost',
    icon: '💰',
    label: '예상 설치비',
    unit: '만원',
    get: s => s['경제성']?.['예상설치비_만원'],
    fmt: v => v?.toLocaleString(),
  },
  {
    key: 'payback',
    icon: '📅',
    label: '단순 회수기간',
    unit: '년',
    get: s => s['경제성']?.['단순회수기간_년'],
    fmt: v => v?.toFixed(1),
  },
  {
    key: 'co2',
    icon: '🌿',
    label: 'CO₂ 저감량',
    unit: 'kg/년',
    get: s => s['경제성']?.['연간CO2저감_kg'],
    fmt: v => v?.toLocaleString(),
  },
]

export default function ResultCards({ summary, htmlPath, pdfPath }) {
  if (!summary) return null

  const monthly = summary['태양광시스템']?.['월별발전량_kWh']
  const notes   = summary['특이사항'] || []
  const address = summary['주소']

  return (
    <div className="result-section">
      <p className="result-address">
        분석 완료: <strong>{address}</strong>
      </p>

      <div className="metric-grid">
        {METRICS.map(m => {
          const raw = m.get(summary)
          const display = raw != null ? m.fmt(raw) : '—'
          return (
            <div key={m.key} className={`metric-card ${m.highlight ? 'highlight' : ''}`}>
              <div className="metric-icon">{m.icon}</div>
              <div className="metric-label">{m.label}</div>
              <div className="metric-value">{display}</div>
              <div className="metric-unit">{m.unit}</div>
            </div>
          )
        })}
      </div>

      <MonthlyChart values={monthly} />

      <div className="section-panel card">
        <p className="section-title">보고서 다운로드</p>
        <DownloadButtons htmlPath={htmlPath} pdfPath={pdfPath} />
      </div>

      {notes.length > 0 && (
        <div className="section-panel card">
          <p className="section-title">특이사항</p>
          <ul className="notes-list">
            {notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </div>
      )}

      <BuildingInfo summary={summary} />
    </div>
  )
}

function BuildingInfo({ summary }) {
  const b = summary['건물정보']
  if (!b) return null
  const rows = [
    ['건물 유형', b['유형']],
    ['층수', b['층수'] ? `${b['층수']}층` : '—'],
    ['지붕 면적', b['지붕면적_m2'] ? `${b['지붕면적_m2']} m²` : '—'],
    ['지붕 형태', b['지붕형태']],
    ['경사각', b['경사각_deg'] ? `${b['경사각_deg']}°` : '—'],
    ['구조', b['구조']],
  ].filter(([, v]) => v && v !== '—')

  const sys = summary['태양광시스템']
  const sysRows = [
    ['패널 수', sys?.['패널수'] ? `${sys['패널수']} 장` : '—'],
    ['인버터 용량', sys?.['인버터용량_kW'] ? `${sys['인버터용량_kW']} kW` : '—'],
    ['직병렬 구성', sys?.['직병렬구성']],
  ].filter(([, v]) => v && v !== '—')

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
      <InfoTable title="건물 정보" rows={rows} />
      <InfoTable title="시스템 구성" rows={sysRows} />
    </div>
  )
}

function InfoTable({ title, rows }) {
  return (
    <div className="section-panel card">
      <p className="section-title">{title}</p>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <td style={{ padding: '5px 0', color: 'var(--text-secondary)', width: '45%' }}>{k}</td>
              <td style={{ padding: '5px 0', fontWeight: 500 }}>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

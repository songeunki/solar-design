import MonthlyChart from './MonthlyChart';
import SolarAltitudeChart from './SolarAltitudeChart';
import PanelLayoutViewer from './PanelLayoutViewer';
import BuildingInfo from './BuildingInfo';
import DownloadButtons from './DownloadButtons';

/**
 * ResultCards
 * props:
 *   result - 분석 결과 객체 (백엔드 /analyze 응답)
 */
export default function ResultCards({ result }) {
  if (!result) return null;

  const {
    building = {},
    system = {},
    financial = {},
    monthly_data = [],
    panel_layout = null,
    report_url,
    pdf_url,
  } = result;

  const kpis = [
    {
      label: '설치 용량',
      value: system.totalKw ?? '-',
      unit: 'kW',
      icon: '⚡',
      cls: 'blue',
    },
    {
      label: '연간 발전량',
      value: system.yearlyTotal ? system.yearlyTotal.toLocaleString() : '-',
      unit: 'kWh',
      icon: '☀️',
      cls: 'orange',
    },
    {
      label: '연간 수익',
      value: financial.yearlyRevenue
        ? `${(financial.yearlyRevenue / 10000).toFixed(0)}만`
        : '-',
      unit: '원',
      icon: '💰',
      cls: 'green',
    },
    {
      label: '투자 회수',
      value: financial.paybackYear ?? '-',
      unit: '년',
      icon: '📈',
      cls: 'blue',
    },
  ];

  return (
    <div className="result-section">
      {/* KPI 카드 */}
      <div className="kpi-grid" style={{ marginBottom: 20 }}>
        {kpis.map((k, i) => (
          <div className="kpi-card" key={i}>
            <div className="kpi-text">
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value">
                {k.value}
                <span className="kpi-unit">{k.unit}</span>
              </div>
            </div>
            <div className={`kpi-icon ${k.cls}`}>{k.icon}</div>
          </div>
        ))}
      </div>

      {/* 메인 컨텐츠 */}
      <div className="result-main-grid">
        {/* 차트 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card card-accent">
            <div className="section-header">
              <div className="section-title-dot" />
              <span className="section-title">📊 월별 예상 발전량</span>
              <div className="badge badge-green" style={{ marginLeft: 'auto' }}>
                <span className="badge-dot" />분석 완료
              </div>
            </div>
            <MonthlyChart data={monthly_data} />
          </div>

          {/* 태양 고도각 */}
          <div className="card card-accent">
            <div className="section-header">
              <div className="section-title-dot" />
              <span className="section-title">☀️ 월별 태양 고도각</span>
            </div>
            <SolarAltitudeChart data={monthly_data} />
          </div>

          {/* 재무 분석 */}
          <div className="card card-accent">
            <div className="section-header">
              <div className="section-title-dot" />
              <span className="section-title">💸 재무 분석</span>
            </div>
            <div style={{ padding: '0 24px 16px' }}>
              {[
                { label: '총 설치비용', value: financial.installCost ? `${(financial.installCost / 10000).toFixed(0)}만원` : '-' },
                { label: '연간 전기 판매 수익', value: financial.yearlyRevenue ? `${(financial.yearlyRevenue / 10000).toFixed(0)}만원` : '-', cls: 'orange' },
                { label: 'REC 수익 (추정)', value: financial.recRevenue ? `${(financial.recRevenue / 10000).toFixed(0)}만원` : '-', cls: 'orange' },
                { label: '투자 회수 기간', value: financial.paybackYear ? `${financial.paybackYear}년` : '-', cls: 'blue' },
                { label: '20년 순수익 (추정)', value: financial.netProfit20y ? `${(financial.netProfit20y / 10000).toFixed(0)}만원` : '-', cls: 'blue' },
              ].map((row, i) => (
                <div className="info-row" key={i}>
                  <span className="info-row-label">{row.label}</span>
                  <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 사이드: 건물 + 시스템 정보 */}
        <BuildingInfo building={building} system={system} />
      </div>

      {/* 패널 배치도 */}
      {panel_layout && (
        <div className="card card-accent" style={{ marginTop: 16 }}>
          <div className="section-header">
            <div className="section-title-dot" />
            <span className="section-title">🔲 태양광 패널 가상 배치도</span>
            <div className="badge badge-blue" style={{ marginLeft: 'auto' }}>
              640W × {panel_layout.stats?.active_panels ?? '-'}매
            </div>
          </div>
          <PanelLayoutViewer layout={panel_layout} />
        </div>
      )}

      {/* 다운로드 */}
      <div className="card" style={{ marginTop: 16 }}>
        <DownloadButtons reportUrl={report_url} pdfUrl={pdf_url} />
      </div>
    </div>
  );
}

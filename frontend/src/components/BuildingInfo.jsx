/**
 * BuildingInfo
 * props:
 *   building - { name, address, floor, area, year, roofType }
 *   system   - { panelCount, totalKw, inverterKw, monthlyAvg, yearlyTotal }
 */
export default function BuildingInfo({ building = {}, system = {} }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* 건물 정보 */}
      <div className="card card-accent">
        <div className="section-header">
          <div className="section-title-dot" />
          <span className="section-title">🏢 건물 정보</span>
        </div>
        <div style={{ padding: '0 24px 16px' }}>
          {[
            { label: '건물명', value: building.name || '-' },
            { label: '주소', value: building.address || '-' },
            { label: '층수', value: building.floor ? `${building.floor}층` : '-' },
            { label: '건축 연도', value: building.year ? `${building.year}년` : '-' },
            { label: '연면적', value: building.area ? `${building.area.toLocaleString()} m²` : '-' },
            { label: '지붕 유형', value: building.roofType || '-' },
          ].map((row, i) => (
            <div className="info-row" key={i}>
              <span className="info-row-label">{row.label}</span>
              <span className="info-row-value">{row.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 시스템 구성 */}
      <div className="card card-accent-orange">
        <div className="section-header">
          <div className="section-title-dot" style={{ background: 'var(--orange)' }} />
          <span className="section-title">⚡ 시스템 구성</span>
        </div>
        <div style={{ padding: '0 24px 8px' }}>
          {[
            { label: '패널 수량', value: system.panelCount ? `${system.panelCount}매` : '-' },
            { label: '설치 용량', value: system.totalKw ? `${system.totalKw} kW` : '-', cls: 'blue' },
            { label: '인버터 용량', value: system.inverterKw ? `${system.inverterKw} kW` : '-' },
            { label: '월 평균 발전량', value: system.monthlyAvg ? `${system.monthlyAvg.toLocaleString()} kWh` : '-', cls: 'orange' },
            { label: '연간 예상 발전량', value: system.yearlyTotal ? `${system.yearlyTotal.toLocaleString()} kWh` : '-', cls: 'orange' },
          ].map((row, i) => (
            <div className="info-row" key={i}>
              <span className="info-row-label">{row.label}</span>
              <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
            </div>
          ))}
        </div>

        {/* 640W 안내문구 */}
        <div className="notice-box" style={{ margin: '0 24px 16px' }}>
          ℹ️ 태양광 모듈 용량은 640W 기준으로 산정하였습니다.
        </div>
      </div>
    </div>
  );
}

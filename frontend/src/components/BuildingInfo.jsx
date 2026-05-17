/**
 * BuildingInfo
 * props:
 *   building - { address, floor, area, archArea, roofType, roofShape,
 *                azimuth, azimuthSource, structure, purpose, irradiation }
 *   system   - { panelCount, totalKw, inverterKw, monthlyAvg, yearlyTotal,
 *                stringConfig, co2Year }
 */
export default function BuildingInfo({ building = {}, system = {} }) {
  const azSrc = building.azimuthSource === 'override' ? '(수동)' : '(자동)';

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
            { label: '주소',       value: building.address || '-' },
            { label: '용도',       value: building.purpose || '-' },
            { label: '층수',       value: building.floor ? `${building.floor}층` : '-' },
            { label: '연면적',     value: building.area ? `${building.area.toLocaleString()} m²` : '-' },
            { label: '건축면적',   value: building.archArea ? `${building.archArea.toLocaleString()} m²` : '-' },
            { label: '지붕 유형',  value: building.roofType || '-' },
            { label: '구조',       value: building.structure || '-' },
            { label: '방위각',     value: building.azimuth != null ? `${building.azimuth}° ${azSrc}` : '-', cls: 'blue' },
            { label: '연간 일사량', value: building.irradiation ? `${building.irradiation} kWh/m²` : '-', cls: 'orange' },
          ].map((row, i) => (
            <div className="info-row" key={i}>
              <span className="info-row-label">{row.label}</span>
              <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 시스템 구성 */}
      <div className="card card-accent">
        <div className="section-header">
          <div className="section-title-dot" />
          <span className="section-title">⚡ 시스템 구성</span>
        </div>
        <div style={{ padding: '0 24px 8px' }}>
          {[
            { label: '패널 수량',       value: system.panelCount ? `${system.panelCount}매` : '-' },
            { label: '설치 용량',       value: system.totalKw ? `${system.totalKw} kW` : '-',                    cls: 'blue' },
            { label: '인버터 용량',     value: system.inverterKw ? `${system.inverterKw} kW` : '-' },
            { label: '직병렬 구성',     value: system.stringConfig || '-' },
            { label: '월 평균 발전량',   value: system.monthlyAvg ? `${system.monthlyAvg.toLocaleString()} kWh` : '-', cls: 'orange' },
            { label: '연간 예상 발전량', value: system.yearlyTotal ? `${system.yearlyTotal.toLocaleString()} kWh` : '-', cls: 'orange' },
            { label: 'CO₂ 연간 절감',   value: system.co2Year ? `${system.co2Year.toLocaleString()} kg` : '-' },
          ].map((row, i) => (
            <div className="info-row" key={i}>
              <span className="info-row-label">{row.label}</span>
              <span className={`info-row-value ${row.cls || ''}`}>{row.value}</span>
            </div>
          ))}
        </div>

        <div className="notice-box" style={{ margin: '0 24px 16px' }}>
          ℹ️ 태양광 모듈 용량은 관리자 설정 기준으로 산정하였습니다.
        </div>
      </div>
    </div>
  );
}

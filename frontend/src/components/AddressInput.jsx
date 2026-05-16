import { useState, useRef } from 'react';

/**
 * AddressInput
 * props:
 *   label       - 입력창 레이블 (기본: "주소 입력")
 *   onSubmit    - 분석 시작 콜백({ address, isRoad })
 *   disabled    - 분석 중 비활성화
 *   placeholder - 입력창 플레이스홀더
 */
const AZ_LABELS = { 90: '동(E)', 135: '남동(SE)', 180: '남(S)', 225: '남서(SW)', 270: '서(W)' };

export default function AddressInput({
  label = '주소 입력',
  onSubmit,
  disabled = false,
  placeholder = '예) 서울 강남구 테헤란로 152 또는 지번 주소',
}) {
  const [address, setAddress]       = useState('');
  const [azimuth, setAzimuth]       = useState(180);
  const [azimuthAuto, setAzimuthAuto] = useState(true);
  const inputRef = useRef(null);

  const isRoadAddress = (addr) => {
    const roadKeywords = ['로', '길', '대로', '번길'];
    return roadKeywords.some((k) => addr.includes(k));
  };

  const handleSubmit = () => {
    const trimmed = address.trim();
    if (!trimmed) {
      inputRef.current?.focus();
      return;
    }
    onSubmit?.({
      address: trimmed,
      isRoad: isRoadAddress(trimmed),
      azimuth_override: azimuthAuto ? null : azimuth,
    });
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') handleSubmit();
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <label
        style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}
      >
        {label}
      </label>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          ref={inputRef}
          className="input-field"
          style={{ flex: 1 }}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
        />
        <button
          className="btn btn-primary"
          onClick={handleSubmit}
          disabled={disabled || !address.trim()}
          style={{ whiteSpace: 'nowrap', flexShrink: 0 }}
        >
          {disabled ? (
            <>
              <span className="spinner" />
              분석 중
            </>
          ) : (
            '🔍 분석'
          )}
        </button>
      </div>
      {address && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', paddingLeft: 2 }}>
          주소 유형:{' '}
          <strong style={{ color: 'var(--blue)' }}>
            {isRoadAddress(address) ? '도로명 주소' : '지번 주소'}
          </strong>
          로 감지
        </div>
      )}

      {/* 방위각 설정 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 2 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
          방위각
        </span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => setAzimuthAuto(a => !a)}
          style={{
            padding: '3px 8px', fontSize: 11, borderRadius: 5, cursor: 'pointer',
            whiteSpace: 'nowrap', border: '1px solid',
            background:   azimuthAuto ? '#1E6FD9' : 'transparent',
            color:        azimuthAuto ? 'white'   : 'var(--text-muted)',
            borderColor:  azimuthAuto ? '#1E6FD9' : 'var(--border)',
          }}
        >
          자동(OSM)
        </button>
        <input
          type="range" min={90} max={270} step={5}
          value={azimuth}
          disabled={disabled || azimuthAuto}
          onChange={e => { setAzimuth(parseInt(e.target.value)); setAzimuthAuto(false); }}
          style={{ flex: 1, accentColor: '#1E6FD9', opacity: azimuthAuto ? 0.35 : 1 }}
        />
        <span style={{
          fontSize: 12, fontWeight: 700, minWidth: 72, textAlign: 'right',
          color: azimuthAuto ? 'var(--text-muted)' : '#1E6FD9',
        }}>
          {azimuthAuto ? '자동' : `${azimuth}° ${AZ_LABELS[azimuth] ?? ''}`}
        </span>
      </div>
    </div>
  );
}

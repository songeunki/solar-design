import { useState, useRef } from 'react';

/**
 * AddressInput
 * props:
 *   label       - 입력창 레이블 (기본: "주소 입력")
 *   onSubmit    - 분석 시작 콜백({ address, isRoad })
 *   disabled    - 분석 중 비활성화
 *   placeholder - 입력창 플레이스홀더
 */
export default function AddressInput({
  label = '주소 입력',
  onSubmit,
  disabled = false,
  placeholder = '예) 서울 강남구 테헤란로 152 또는 지번 주소',
}) {
  const [address, setAddress] = useState('');
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
    onSubmit?.({ address: trimmed, isRoad: isRoadAddress(trimmed) });
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
    </div>
  );
}

function detectAddressType(addr) {
  if (!addr) return null
  return /(로|길)\s*\d/.test(addr) ? 'road' : 'lot'
}

function SearchIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <circle cx="6" cy="6" r="4" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 10l2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )
}

export default function AddressInput({ value, onChange, onSubmit, disabled, placeholder }) {
  const type = detectAddressType(value)

  function handleKey(e) {
    if (e.key === 'Enter' && !disabled && value.trim()) onSubmit()
  }

  return (
    <div className="address-field">
      <span className="address-icon"><SearchIcon /></span>
      <input
        className="address-input"
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKey}
        placeholder={placeholder || '예) 서울특별시 강남구 테헤란로 152 또는 역삼동 737'}
        disabled={disabled}
      />
      {type && value.length > 4 && (
        <span className={`addr-type-badge ${type === 'road' ? 'addr-type-road' : 'addr-type-lot'}`}>
          {type === 'road' ? '도로명' : '지번'}
        </span>
      )}
    </div>
  )
}

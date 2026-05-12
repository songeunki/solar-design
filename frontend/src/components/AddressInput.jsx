import { useState } from 'react'

function detectAddressType(addr) {
  if (!addr) return null
  const roadPattern = /(로|길)\s*\d/
  return roadPattern.test(addr) ? 'road' : 'lot'
}

export default function AddressInput({ value, onChange, onSubmit, disabled, placeholder }) {
  const type = detectAddressType(value)

  function handleKey(e) {
    if (e.key === 'Enter' && !disabled && value.trim()) onSubmit()
  }

  return (
    <div className="address-input-wrap">
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

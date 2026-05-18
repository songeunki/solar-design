// 백엔드 베이스 URL.
// 프로덕션(Vercel): VITE_API_URL = https://solar-design-api.onrender.com
// 개발(로컬): 빈 문자열 → 상대경로 → Vite proxy가 localhost:8001 로 전달
const _base = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export const HTTP_BASE = _base;

export const WS_BASE = _base
  ? _base.replace(/^https/, 'wss').replace(/^http/, 'ws')
  : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}`;

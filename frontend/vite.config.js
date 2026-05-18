import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // 로컬 개발 시 API/WebSocket 요청을 백엔드(8001)로 프록시
      '/ws':      { target: 'ws://localhost:8001',   ws: true,         changeOrigin: true },
      '/files':   { target: 'http://localhost:8001',                   changeOrigin: true },
      '/analyze': { target: 'http://localhost:8001',                   changeOrigin: true },
      '/compare': { target: 'http://localhost:8001',                   changeOrigin: true },
      '/health':       { target: 'http://localhost:8001', changeOrigin: true },
      '/api/ordinance': { target: 'http://localhost:8001', changeOrigin: true },
    },
  },
})

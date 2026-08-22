import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5175,
    // 라이브 모드: server/app.py (uvicorn, :8010) 로 프록시.
    // 정적 모드(plan.json)만 쓸 때는 서버가 없어도 된다.
    proxy: {
      '/api': 'http://localhost:8010',
      '/route': 'http://localhost:8010',
    },
  },
})

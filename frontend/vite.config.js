import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend origin used by the dev-server proxy.
// Local:  http://127.0.0.1:8000 (default)
// Docker: http://backend:8000 (set VITE_BACKEND_TARGET in docker-compose)
const backendTarget = process.env.VITE_BACKEND_TARGET || 'http://127.0.0.1:8000'
const wsTarget = backendTarget.replace(/^http/, 'ws')

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/settings': backendTarget,
      '/parts': backendTarget,
      '/sessions': backendTarget,
      '/download': backendTarget,
      '/sync': backendTarget,
      '/system': backendTarget,
      '/chat': {
        target: wsTarget,
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
})

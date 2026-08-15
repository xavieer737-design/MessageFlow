import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to the FastAPI backend so the browser
// only ever talks to the same origin (no CORS issues, cookies work).
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // The live-preview environment uses a per-session hostname.
    allowedHosts: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        // The Android device channel (/api/devices/ws) is a WebSocket, so the
        // dev proxy must forward protocol upgrades too - otherwise a phone
        // paired against the dev server can pair but never connect.
        ws: true,
        // changeOrigin rewrites Host to the target, so the backend would
        // otherwise believe it lives at 127.0.0.1:8000 and embed that
        // unreachable address in the Android pairing QR code. Forward the
        // address the browser actually used so the QR points at this
        // machine (e.g. http://192.168.1.50:8000 over the LAN).
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            const host = req.headers.host
            if (host) {
              proxyReq.setHeader('x-forwarded-host', host)
              proxyReq.setHeader('x-forwarded-proto', 'http')
            }
          })
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    css: false,
  },
})

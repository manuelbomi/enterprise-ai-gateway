// ============================================================
// vite.config.ts — Vite build configuration
//
// ARCHITECT'S NOTE:
//   Vite is the modern frontend build tool — it replaces Create React App
//   with dramatically faster cold starts and HMR (hot module replacement).
//
//   The proxy config here solves the CORS problem in local development:
//   The browser makes requests to http://localhost:5173/api/...
//   Vite forwards them to http://localhost:8000/...
//   This means the browser never sees cross-origin requests in dev.
//   In production, nginx handles this same proxying role.
// ============================================================

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],

  // Path aliases — import from "@/components/..." instead of "../../components/..."
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    port: 5173,
    proxy: {
      // Forward /api calls to FastAPI backend in development
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },

  build: {
    outDir: 'dist',
    sourcemap: false,       // disable in production for smaller bundles
    chunkSizeWarningLimit: 1000,
  },
})

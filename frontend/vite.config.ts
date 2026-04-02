import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: process.env.API_TARGET || 'http://localhost:8001',
        changeOrigin: true
      },
      '/v1': {
        target: process.env.API_TARGET || 'http://localhost:8001',
        changeOrigin: true
      },
      '/health': {
        target: process.env.API_TARGET || 'http://localhost:8001',
        changeOrigin: true
      },
      '/mcp': {
        target: process.env.API_TARGET || 'http://localhost:8002',
        changeOrigin: true
      }
    }
  }
})

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 3000,
    allowedHosts: ['.monkeycode-ai.online'],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('echarts')) return 'echarts'
          if (id.includes('d3')) return 'd3'
          if (id.includes('node_modules/vue') || id.includes('node_modules/pinia')) return 'vendor'
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
})

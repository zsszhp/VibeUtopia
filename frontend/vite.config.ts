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
        manualChunks: {
          // echarts 单独打包，避免主 bundle 过大
          echarts: ['echarts'],
          // d3 单独打包
          d3: ['d3'],
          // 图表相关组件
          vendor: ['vue', 'pinia'],
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
})

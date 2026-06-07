import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.tsx',
    exclude: ['**/node_modules/**', '**/dist/**', '**/e2e-tests/**', '**/.{idea,git,cache,output,temp}/**'],
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8006',
        changeOrigin: true,
        secure: false,
        ws: true
      }
    }
  }
});
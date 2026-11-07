import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Load every variable (prefix '') from .env files and the process environment so the
  // dev-server proxy target can be set without a VITE_ prefix (it is server-side only).
  const env = loadEnv(mode, process.cwd(), '');
  // Where the Vite dev server forwards /api (and websocket) requests.
  // Local dev: http://localhost:8006. Docker compose: http://backend:8006.
  const apiProxyTarget = env.API_PROXY_TARGET || 'http://localhost:8006';

  return {
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
          target: apiProxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true
        }
      }
    }
  };
});

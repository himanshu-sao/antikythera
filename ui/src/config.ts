/// <reference types="vite/client" />

// API base URL. Vite only exposes VITE_-prefixed variables to browser code, and only through
// import.meta.env (process.env does not exist in the browser). An empty string means
// "same origin", so requests like `${apiUrl}/api/...` go through the Vite dev-server proxy
// (see API_PROXY_TARGET in vite.config.ts) or a reverse proxy in production.
const apiUrl: string = import.meta.env.VITE_API_URL || '';
export { apiUrl };

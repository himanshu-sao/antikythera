const procEnv = (globalThis as any).process?.env;
let apiUrl = (procEnv && procEnv.VITE_API_URL) ? procEnv.VITE_API_URL : 'http://localhost:8006';
export { apiUrl };


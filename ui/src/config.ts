const procEnv = (globalThis as any).process?.env;
let apiUrl = (procEnv && procEnv.VITE_API_URL) ? procEnv.VITE_API_URL : '' ;
export { apiUrl };


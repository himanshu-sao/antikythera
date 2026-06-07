const metaEnv = typeof import.meta !== "undefined" && (import.meta as any).env ? (import.meta as any).env : {};
export const apiUrl = (metaEnv as any).VITE_API_URL ?? (globalThis as any)?.process?.env?.VITE_API_URL ?? 'http://localhost:8000';

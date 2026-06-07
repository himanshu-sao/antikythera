export const apiUrl = (import.meta.env as any)?.VITE_API_URL ?? (globalThis as any)?.process?.env?.VITE_API_URL ?? 'http://localhost:8000';

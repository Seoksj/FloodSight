// 프로덕션(GitHub Pages)에서는 VITE_API_BASE_URL 환경변수로 Render URL 주입
// 개발환경에서는 vite.config.js 프록시가 /api/* 를 localhost:8000으로 처리
const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export const apiFetch = (path) => fetch(`${BASE}${path}`);

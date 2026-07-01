// 프로덕션(GitHub Pages): VITE_API_BASE_URL → 학교 서버 URL
// 개발환경: vite.config.js 프록시가 /api/* → localhost:8000 처리
const SERVER_URL = "http://165.246.170.53:8001";
const BASE = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.PROD ? SERVER_URL : "");

export const apiFetch = (path) =>
  fetch(BASE ? `${BASE}${path.replace(/^\/api/, "")}` : path);

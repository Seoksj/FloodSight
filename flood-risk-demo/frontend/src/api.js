// 프로덕션(GitHub Pages)에서는 VITE_API_BASE_URL 환경변수로 Render URL 주입
// 개발환경에서는 vite.config.js 프록시가 /api/* 를 localhost:8000으로 처리
const RENDER_URL = "https://floodsight-ke6a.onrender.com";
const BASE = import.meta.env.VITE_API_BASE_URL
  || (import.meta.env.PROD ? RENDER_URL : "");

// dev: BASE 없음 → vite 프록시가 /api/* → localhost:8000/* 처리
// prod: BASE 있음 → /api 접두사 제거 후 Render URL에 직접 요청
export const apiFetch = (path) =>
  fetch(BASE ? `${BASE}${path.replace(/^\/api/, "")}` : path);

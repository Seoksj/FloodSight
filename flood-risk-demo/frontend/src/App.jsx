import React, { useEffect, useState } from "react";
import MapView from "./components/MapView.jsx";
import LocationPanel from "./components/LocationPanel.jsx";
import DistrictPanel from "./components/DistrictPanel.jsx";
import LegendBar from "./components/LegendBar.jsx";
import { useTheme } from "./ThemeContext.jsx";
import { apiFetch } from "./api.js";

const HORIZONS = [
  { key: "current", label: "현재" },
  { key: "1h",      label: "1시간 후" },
  { key: "3h",      label: "3시간 후" },
];

const GRADE_COLORS = {
  안전: "#22c55e", 주의: "#eab308", 경보: "#f97316", 위험: "#ef4444",
};

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  );
}

export default function App() {
  const { theme, c, toggle } = useTheme();
  const [health,      setHealth]      = useState(null);
  const [stats,       setStats]       = useState(null);
  const [horizon,     setHorizon]     = useState("current");
  const [highlightId, setHighlightId] = useState(null);

  useEffect(() => {
    const load = async () => {
      try { const r = await apiFetch("/api/health"); if (r.ok) setHealth(await r.json()); } catch {}
    };
    load();
    const id = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const load = async () => {
      try {
        const r = await apiFetch("/api/districts");
        if (!r.ok) return;
        const { districts } = await r.json();
        const counts = { 안전: 0, 주의: 0, 경보: 0, 위험: 0 };
        districts.forEach(d => { if (counts[d.grade] !== undefined) counts[d.grade]++; });
        setStats(counts);
      } catch {}
    };
    load();
    const id = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  const alertTotal = stats ? (stats["경보"] + stats["위험"]) : 0;

  return (
    <div className="flex flex-col h-screen overflow-hidden" style={{ background: c.bgBase, color: c.textPrimary }}>

      {/* ── Header ─────────────────────────────────────────────── */}
      <header style={{ background: c.bgSurface, borderBottom: `1px solid ${c.borderMid}` }}
        className="flex items-center gap-3 px-5 h-14 shrink-0">

        {/* 로고 */}
        <div className="flex items-center gap-2.5 shrink-0">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center"
               style={{ background: "linear-gradient(135deg,#1d4ed8,#2563eb)", boxShadow: "0 2px 8px rgba(37,99,235,0.4)" }}>
            <svg className="w-4 h-4 text-white" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/>
            </svg>
          </div>
          <div>
            <div className="text-sm font-bold leading-none" style={{ color: c.textPrimary }}>FloodSight</div>
            <div className="text-[10px] leading-none mt-0.5" style={{ color: c.textFaint }}>도시 침수 위험 모니터링</div>
          </div>
        </div>

        {/* 예보 시간대 토글 */}
        <div className="flex items-center gap-1 ml-2 p-1 rounded-xl"
             style={{ background: c.toggleTrack, border: `1px solid ${c.border}` }}>
          {HORIZONS.map(({ key, label }) => (
            <button key={key} onClick={() => setHorizon(key)}
              className="text-xs px-3 py-1.5 rounded-lg font-medium transition-all duration-200"
              style={horizon === key ? {
                background: "linear-gradient(135deg,#1d4ed8,#2563eb)",
                color: "#fff",
                boxShadow: "0 2px 8px rgba(37,99,235,0.4)",
              } : { color: c.textMuted }}>
              {label}
            </button>
          ))}
        </div>

        {horizon !== "current" && (
          <span className="text-xs px-2 py-1 rounded-md font-medium"
                style={{ background: c.pillActive, color: c.pillText, border: `1px solid ${c.pillActiveBorder}` }}>
            예보 데이터
          </span>
        )}

        <div className="flex-1" />

        {/* 등급별 통계 */}
        {stats && (
          <div className="hidden md:flex items-center gap-4">
            {["위험", "경보", "주의", "안전"].map(g => (
              <div key={g} className="flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: GRADE_COLORS[g] }} />
                <span className="text-xs" style={{ color: c.textMuted }}>{g}</span>
                <span className="text-sm font-bold" style={{ color: GRADE_COLORS[g] }}>{stats[g]}</span>
              </div>
            ))}
          </div>
        )}

        <div className="hidden md:block w-px h-5 mx-1" style={{ background: c.borderMid }} />
        <LegendBar />
        <div className="w-px h-5 mx-1" style={{ background: c.borderMid }} />

        {/* 서버 상태 */}
        {health && (
          <div className="flex items-center gap-1.5 text-xs" style={{ color: c.textFaint }}>
            <span className={`w-1.5 h-1.5 rounded-full ${health.cache_ready ? "" : "danger-pulse"}`}
                  style={{ background: health.cache_ready ? "#22c55e" : "#eab308" }} />
            <span className="hidden lg:inline">
              {health.cache_ready ? `${health.district_count}개 지구` : "수집 중"}
            </span>
          </div>
        )}

        {/* 경보 뱃지 */}
        {alertTotal > 0 && (
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold danger-pulse"
               style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.25)" }}>
            ⚠ {alertTotal}
          </div>
        )}

        {/* 다크/라이트 토글 */}
        <button onClick={toggle}
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-all"
          style={{ background: c.bgInput, border: `1px solid ${c.border}`, color: c.textMuted }}
          title={theme === "dark" ? "라이트 모드" : "다크 모드"}>
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>
      </header>

      {/* ── Body ─────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">

        {/* 사이드패널 */}
        <aside className="w-[340px] shrink-0 flex flex-col overflow-hidden"
               style={{ background: c.bgSurface, borderRight: `1px solid ${c.borderMid}` }}>
          <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-5">
            <LocationPanel />
            <div style={{ height: "1px", background: c.border }} />
            <DistrictPanel highlightId={highlightId} horizon={horizon} />
          </div>
        </aside>

        {/* 지도 */}
        <main className="flex-1 relative">
          <MapView horizon={horizon} onDistrictSelect={(p) => setHighlightId(p.id)} />
        </main>
      </div>
    </div>
  );
}

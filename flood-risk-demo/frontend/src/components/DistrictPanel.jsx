import React, { useEffect, useState } from "react";
import { useTheme } from "../ThemeContext.jsx";
import { apiFetch } from "../api.js";

const GRADE_CFG = {
  안전: { color: "#22c55e", bg: "rgba(34,197,94,0.10)",   border: "rgba(34,197,94,0.22)"  },
  주의: { color: "#eab308", bg: "rgba(234,179,8,0.10)",   border: "rgba(234,179,8,0.22)"  },
  경보: { color: "#f97316", bg: "rgba(249,115,22,0.10)",  border: "rgba(249,115,22,0.22)" },
  위험: { color: "#ef4444", bg: "rgba(239,68,68,0.12)",   border: "rgba(239,68,68,0.28)"  },
};
const GRADE_ORDER = { 위험: 0, 경보: 1, 주의: 2, 안전: 3 };
const HORIZON_LABEL = { current: "현재", "1h": "1시간 후", "3h": "3시간 후" };

function GradePill({ grade }) {
  const cfg = GRADE_CFG[grade] ?? GRADE_CFG["안전"];
  return (
    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md"
          style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
      {grade}
    </span>
  );
}

function RainBar({ rainfall, capacity, grade }) {
  const { c } = useTheme();
  const cfg    = GRADE_CFG[grade] ?? GRADE_CFG["안전"];
  const pct    = Math.min(rainfall / Math.max(capacity, 1) * 100, 100);
  const isOver = rainfall > capacity;
  return (
    <div className="relative h-1.5 rounded-full overflow-hidden" style={{ background: c.border }}>
      <div className="absolute inset-y-0 left-0 rounded-full gauge-bar"
           style={{
             width: `${pct}%`,
             background: cfg.color,
             boxShadow: isOver ? `0 0 6px ${cfg.color}` : "none",
           }} />
    </div>
  );
}

export default function DistrictPanel({ highlightId, horizon = "current" }) {
  const { c } = useTheme();
  const [districts,   setDistricts]  = useState([]);
  const [loading,     setLoading]    = useState(true);
  const [cityFilter,  setCity]       = useState("전체");
  const [gradeFilter, setGrade]      = useState("전체");

  const fetchData = async () => {
    try {
      const res = await apiFetch("/api/districts");
      if (res.ok) setDistricts((await res.json()).districts ?? []);
    } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => { setGrade("전체"); }, [horizon]);

  const getDisp = (d) => {
    if (horizon === "current") return { grade: d.grade, rainfall: d.rainfall_1h, score: d.risk_score };
    const fc = d.forecast?.[horizon];
    return { grade: fc?.grade ?? d.grade, rainfall: fc?.rainfall ?? d.rainfall_1h, score: fc?.risk_score ?? d.risk_score };
  };

  const cities = ["전체", ...new Set(districts.map(d => d.city))];
  let visible = [...districts];
  if (cityFilter !== "전체")  visible = visible.filter(d => d.city === cityFilter);
  if (gradeFilter !== "전체") visible = visible.filter(d => getDisp(d).grade === gradeFilter);
  visible.sort((a, b) => (GRADE_ORDER[getDisp(a).grade] ?? 4) - (GRADE_ORDER[getDisp(b).grade] ?? 4));

  const alertCnt = districts.filter(d => ["경보","위험"].includes(getDisp(d).grade)).length;
  const gradeCounts = { 위험: 0, 경보: 0, 주의: 0, 안전: 0 };
  districts.forEach(d => { const g = getDisp(d).grade; if (gradeCounts[g] !== undefined) gradeCounts[g]++; });

  if (loading) return (
    <div className="flex flex-col gap-2">
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-20 rounded-xl animate-pulse" style={{ background: c.bgCard }} />
      ))}
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wide" style={{ color: c.textMuted }}>
          침수 취약 지구
          {horizon !== "current" && (
            <span className="ml-1.5" style={{ color: c.pillText }}>· {HORIZON_LABEL[horizon]}</span>
          )}
        </span>
        {alertCnt > 0 && (
          <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md danger-pulse"
                style={{ background: "rgba(239,68,68,0.12)", color: "#f87171", border: "1px solid rgba(239,68,68,0.25)" }}>
            ⚠ {alertCnt}곳
          </span>
        )}
      </div>

      {/* 등급 요약 */}
      <div className="grid grid-cols-4 gap-1.5">
        {["위험","경보","주의","안전"].map(g => {
          const cfg    = GRADE_CFG[g];
          const active = gradeFilter === g;
          return (
            <button key={g} onClick={() => setGrade(active ? "전체" : g)}
              className="rounded-lg py-2 text-center transition-all"
              style={{
                background: active ? cfg.bg : c.bgCard,
                border: `1px solid ${active ? cfg.border : c.border}`,
              }}>
              <div className="text-sm font-bold" style={{ color: active ? cfg.color : c.textMuted }}>
                {gradeCounts[g]}
              </div>
              <div className="text-[10px] mt-0.5" style={{ color: active ? cfg.color : c.textFaint }}>{g}</div>
            </button>
          );
        })}
      </div>

      {/* 도시 필터 */}
      <div className="flex gap-1 flex-wrap">
        {cities.map(c_ => (
          <button key={c_} onClick={() => setCity(c_)}
            className="pill text-[11px]"
            style={cityFilter === c_
              ? { background: c.pillActive, color: c.pillText, borderColor: c.pillActiveBorder }
              : { background: c.bgCard, color: c.textMuted, borderColor: c.border }}>
            {c_}
          </button>
        ))}
      </div>

      {/* 리스트 */}
      <div className="flex flex-col gap-1.5 overflow-y-auto" style={{ maxHeight: "calc(100vh - 500px)" }}>
        {visible.length === 0 && (
          <div className="text-center py-8 text-xs" style={{ color: c.textFaint }}>
            해당 조건의 지구가 없습니다
          </div>
        )}
        {visible.map(d => {
          const disp   = getDisp(d);
          const cfg    = GRADE_CFG[disp.grade] ?? GRADE_CFG["안전"];
          const overMm = Math.round((disp.rainfall - d.drainage_capacity) * 10) / 10;
          const isOver = disp.rainfall > d.drainage_capacity;
          const isHL   = highlightId === d.id;

          return (
            <div key={d.id}
              className="rounded-xl px-3 py-2.5 transition-all"
              style={{
                background: isHL ? cfg.bg : c.bgCard,
                border: `1px solid ${isHL ? cfg.border : c.border}`,
              }}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: cfg.color }} />
                  <span className="text-sm font-semibold truncate" style={{ color: c.textPrimary }}>{d.name}</span>
                  <span className="text-[11px] shrink-0" style={{ color: c.textFaint }}>{d.gu}</span>
                </div>
                <GradePill grade={disp.grade} />
              </div>

              <RainBar rainfall={disp.rainfall} capacity={d.drainage_capacity} grade={disp.grade} />

              <div className="flex items-center justify-between mt-1.5 text-[11px]">
                <span style={{ color: c.textMuted }}>
                  {disp.rainfall}mm <span style={{ color: c.textFaint }}>/</span> {d.drainage_capacity}mm
                </span>
                <span style={{ color: isOver ? "#f87171" : "#4ade80", fontWeight: 600 }}>
                  {isOver ? `+${overMm}mm 초과` : `여유 ${Math.abs(overMm)}mm`}
                </span>
              </div>

              {d.flood_history >= 0.8 && (
                <div className="mt-1.5 text-[10px] flex items-center gap-1" style={{ color: "#f97316" }}>
                  <span>●</span><span>과거 침수 이력 높음</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

import React, { useState, useCallback } from "react";
import { useTheme } from "../ThemeContext.jsx";
import { apiFetch } from "../api.js";

const GRADE_CFG = {
  안전: { color: "#22c55e", bg: "rgba(34,197,94,0.08)",   border: "rgba(34,197,94,0.20)"  },
  주의: { color: "#eab308", bg: "rgba(234,179,8,0.08)",   border: "rgba(234,179,8,0.20)"  },
  경보: { color: "#f97316", bg: "rgba(249,115,22,0.08)",  border: "rgba(249,115,22,0.20)" },
  위험: { color: "#ef4444", bg: "rgba(239,68,68,0.10)",   border: "rgba(239,68,68,0.25)"  },
};

function ScoreArc({ score, color }) {
  const pct  = Math.min(score, 1);
  const r    = 36;
  const circ = 2 * Math.PI * r;
  const dash = circ * 0.75;
  const fill = dash * pct;
  const { c } = useTheme();

  return (
    <svg width="96" height="72" viewBox="0 0 96 72">
      <circle cx="48" cy="56" r={r} fill="none"
        stroke={c.border} strokeWidth="7"
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-135 48 56)" />
      <circle cx="48" cy="56" r={r} fill="none"
        stroke={color} strokeWidth="7"
        strokeDasharray={`${fill} ${circ}`}
        strokeLinecap="round"
        transform="rotate(-135 48 56)"
        style={{ transition: "stroke-dasharray 0.6s cubic-bezier(0.4,0,0.2,1)" }} />
      <text x="48" y="52" textAnchor="middle" fontSize="18" fontWeight="700" fill={color}>
        {Math.round(score * 100)}
      </text>
      <text x="48" y="64" textAnchor="middle" fontSize="9" fill={c.textFaint}>점</text>
    </svg>
  );
}

export default function LocationPanel() {
  const { c } = useTheme();
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [result,  setResult]  = useState(null);

  const detect = useCallback(() => {
    setError(null); setLoading(true);
    if (!navigator.geolocation) {
      setError("위치 정보를 지원하지 않는 브라우저입니다.");
      return setLoading(false);
    }
    navigator.geolocation.getCurrentPosition(
      async ({ coords: { latitude: lat, longitude: lon } }) => {
        try {
          const res = await apiFetch(`/api/risk/point?lat=${lat}&lon=${lon}`);
          if (!res.ok) {
            let msg = `HTTP ${res.status}`;
            try { msg = (await res.json()).detail ?? msg; } catch {}
            throw new Error(msg);
          }
          setResult({ ...(await res.json()), fetchedAt: new Date() });
        } catch (e) { setError(e.message); }
        finally { setLoading(false); }
      },
      (e) => { setError(`위치 권한 오류: ${e.message}`); setLoading(false); },
      { timeout: 10000 }
    );
  }, []);

  const cfg    = result ? (GRADE_CFG[result.grade] ?? GRADE_CFG["안전"]) : null;
  const overMm = result ? Math.round((result.rainfall_1h - result.drainage_capacity) * 10) / 10 : 0;
  const isOver = result && result.rainfall_1h > result.drainage_capacity;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold tracking-wide" style={{ color: c.textMuted }}>내 위치 위험도</span>
        <button onClick={detect} disabled={loading}
          className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1.5 rounded-lg transition-all"
          style={loading
            ? { background: c.bgInput, color: c.textFaint, cursor: "not-allowed" }
            : { background: c.pillActive, color: c.pillText, border: `1px solid ${c.pillActiveBorder}` }}>
          {loading
            ? <><svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>탐색 중</>
            : <><svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a2 2 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>내 위치</>
          }
        </button>
      </div>

      {error && (
        <div className="text-xs px-3 py-2 rounded-lg"
             style={{ background: "rgba(239,68,68,0.08)", color: "#f87171", border: "1px solid rgba(239,68,68,0.2)" }}>
          {error}
        </div>
      )}

      {result && cfg && (
        <div className="rounded-xl p-4" style={{ background: cfg.bg, border: `1px solid ${cfg.border}` }}>
          <div className="flex items-center gap-3 mb-3">
            <ScoreArc score={result.risk_score} color={cfg.color} />
            <div className="flex-1">
              <div className="text-xl font-bold" style={{ color: cfg.color }}>{result.grade}</div>
              <div className="text-sm font-medium mt-0.5" style={{ color: c.textPrimary }}>
                {result.nearest_district?.name}
              </div>
              <div className="text-xs mt-0.5" style={{ color: c.textMuted }}>
                {result.nearest_district?.city} {result.nearest_district?.gu}
                {result.nearest_district?.distance_km && ` · ${result.nearest_district.distance_km}km`}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 mb-3">
            {[
              { label: "강수량",     value: `${result.rainfall_1h}mm/hr` },
              { label: "하수도 용량", value: `${result.drainage_capacity}mm/hr` },
              {
                label: "배수 상태",
                value: isOver ? `+${overMm}mm 초과` : `여유 ${Math.abs(overMm)}mm`,
                color: isOver ? "#f87171" : "#4ade80",
              },
              { label: "위험 점수", value: `${Math.round(result.risk_score * 100)}점`, color: cfg.color },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg px-3 py-2" style={{ background: c.bgNum }}>
                <div className="text-[10px] mb-0.5" style={{ color: c.textFaint }}>{label}</div>
                <div className="text-xs font-semibold" style={{ color: color || c.textPrimary }}>{value}</div>
              </div>
            ))}
          </div>

          <p className="text-xs leading-relaxed" style={{ color: c.textMuted }}>{result.reason}</p>
          <div className="mt-2 text-[10px]" style={{ color: c.textFaint }}>
            {result.fetchedAt?.toLocaleString("ko-KR")} 기준
          </div>
        </div>
      )}

      {!result && !loading && !error && (
        <div className="rounded-xl p-5 text-center" style={{ background: c.bgCard, border: `1px solid ${c.border}` }}>
          <div className="w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-3"
               style={{ background: c.pillActive }}>
            <svg className="w-5 h-5" style={{ color: c.pillText }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M17.657 16.657L13.414 20.9a2 2 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </div>
          <p className="text-xs" style={{ color: c.textMuted }}>
            버튼을 눌러 현재 위치의<br/>침수 위험도를 확인하세요
          </p>
        </div>
      )}
    </div>
  );
}

import React, { useEffect, useState, useCallback } from "react";
import { useTheme, gradeStyle, GRADE_MAP } from "./ThemeContext.jsx";
import { apiFetch } from "./api.js";
import MapView from "./components/MapView.jsx";
import DistrictPanel from "./components/DistrictPanel.jsx";
import DistrictDetail from "./components/DistrictDetail.jsx";
import LocationPanel from "./components/LocationPanel.jsx";

const HORIZONS = [
  { key: "current", label: "현재" },
  { key: "1h",      label: "1시간 후" },
  { key: "3h",      label: "3시간 후" },
];

export default function App() {
  const { theme, c, toggle } = useTheme();

  const [horizon,    setHorizon]    = useState("current");
  const [districts,  setDistricts]  = useState([]);
  const [health,     setHealth]     = useState(null);
  const [panel,      setPanel]      = useState("list"); // "list"|"district"|"location"
  const [selected,   setSelected]   = useState(null);  // 선택된 지구 data
  const [alertsOpen, setAlertsOpen] = useState(false);

  // 지구 목록 폴링
  const loadDistricts = useCallback(async () => {
    try {
      const r = await apiFetch("/api/districts");
      if (r.ok) setDistricts((await r.json()).districts ?? []);
    } catch {}
  }, []);

  useEffect(() => {
    loadDistricts();
    const id = setInterval(loadDistricts, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [loadDistricts]);

  useEffect(() => {
    const load = async () => {
      try { const r = await apiFetch("/api/health"); if (r.ok) setHealth(await r.json()); } catch {}
    };
    load();
    const id = setInterval(load, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  // horizon 변경 시 선택 초기화
  useEffect(() => { setPanel("list"); setSelected(null); }, [horizon]);

  const openDistrict = useCallback((d) => {
    setSelected(d);
    setPanel("district");
    setAlertsOpen(false);
  }, []);

  // 현재 horizon 기준 표시용 데이터
  const getDisp = (d) => {
    if (horizon === "current") return { grade: d.grade, rainfall: d.rainfall_1h, score: d.risk_score };
    const fc = d.forecast?.[horizon];
    return { grade: fc?.grade ?? d.grade, rainfall: fc?.rainfall ?? d.rainfall_1h, score: fc?.risk_score ?? d.risk_score };
  };

  const counts = { 위험: 0, 경보: 0, 주의: 0, 안전: 0 };
  districts.forEach(d => { const g = getDisp(d).grade; if (counts[g] !== undefined) counts[g]++; });
  const alertCount = counts["위험"] + counts["경보"];

  const alertDistricts = districts
    .filter(d => ["위험","경보"].includes(getDisp(d).grade))
    .sort((a, b) => getDisp(b).score - getDisp(a).score);

  // ── 스타일 헬퍼 ─────────────────────────────────
  const segBtn = (active) => ({
    height: 30, padding: "0 13px", border: "none", borderRadius: 8,
    fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
    background: active ? c.primary : "transparent",
    color: active ? "#fff" : c.text2, transition: "all .15s",
  });

  const GRADE_COLORS = {
    안전: c.safe, 주의: c.caution, 경보: c.alert, 위험: c.danger,
  };

  return (
    <div style={{ height: "100vh", width: "100%", display: "flex", flexDirection: "column",
                  overflow: "hidden", background: c.bg, color: c.text,
                  fontFamily: "'Pretendard',-apple-system,sans-serif" }}>

      {/* ── HEADER ── */}
      <header style={{ display: "flex", alignItems: "center", gap: 16, padding: "10px 20px",
                       borderBottom: `1px solid ${c.border}`, background: c.surface,
                       flexShrink: 0, zIndex: 100 }}>

        {/* 로고 */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10,
                        background: `linear-gradient(150deg,${c.primary},${c.primary}cc)`,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        boxShadow: `0 4px 12px ${c.primary}44` }}>
            <div style={{ width: 13, height: 13, background: "#fff",
                          borderRadius: "0 50% 50% 50%", transform: "rotate(45deg)" }} />
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: "-.02em", lineHeight: 1.1 }}>FloodSight</div>
            <div style={{ fontSize: 11, color: c.text3, fontWeight: 500, marginTop: 1 }}>도시 침수 위험 모니터링</div>
          </div>
        </div>

        {/* 시간대 토글 */}
        <div style={{ display: "flex", alignItems: "center", gap: 3,
                      background: c.surface2, border: `1px solid ${c.border}`,
                      padding: 3, borderRadius: 10, flexShrink: 0 }}>
          {HORIZONS.map(({ key, label }) => (
            <button key={key} onClick={() => setHorizon(key)} style={segBtn(horizon === key)}>
              {label}
            </button>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* 등급 범례 */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          {["안전","주의","경보","위험"].map(g => (
            <div key={g} style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12.5, fontWeight: 600 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: GRADE_COLORS[g] }} />
              <span style={{ color: c.text2 }}>{g}</span>
            </div>
          ))}
          <div style={{ width: 1, height: 18, background: c.border }} />
          <div style={{ fontSize: 12.5, fontWeight: 600, color: c.text2 }}>
            {health ? `${health.district_count}개 지구` : "연결 중"}
          </div>
        </div>

        {/* 경보 버튼 */}
        {alertCount > 0 && (
          <button onClick={() => setAlertsOpen(true)}
            className="pulse-ring"
            style={{ display: "flex", alignItems: "center", gap: 5, height: 34, padding: "0 12px",
                     border: `1px solid ${c.danger}`, background: c.dangerSoft, color: c.danger,
                     borderRadius: 9, fontWeight: 700, fontSize: 13, cursor: "pointer",
                     fontFamily: "inherit" }}>
            ⚠ {alertCount}
          </button>
        )}

        {/* 다크 토글 */}
        <button onClick={toggle}
          style={{ width: 34, height: 34, border: `1px solid ${c.border}`, background: c.surface2,
                   borderRadius: 9, cursor: "pointer", display: "flex", alignItems: "center",
                   justifyContent: "center", fontSize: 15, color: c.text2 }}>
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </header>

      {/* ── BODY ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", minHeight: 0 }}>

        {/* 사이드 패널 */}
        <aside style={{ width: 380, flexShrink: 0, height: "100%", overflowY: "auto",
                        overflowX: "hidden", borderRight: `1px solid ${c.border}`,
                        background: c.surface, scrollbarWidth: "thin" }}>
          {panel === "list" && (
            <DistrictPanel
              districts={districts}
              horizon={horizon}
              getDisp={getDisp}
              onDistrictClick={openDistrict}
              onLocationClick={() => setPanel("location")}
            />
          )}
          {panel === "district" && selected && (
            <DistrictDetail
              district={selected}
              horizon={horizon}
              getDisp={getDisp}
              onBack={() => setPanel("list")}
            />
          )}
          {panel === "location" && (
            <LocationPanel onBack={() => setPanel("list")} onDistrictClick={openDistrict} />
          )}
        </aside>

        {/* 지도 */}
        <main style={{ flex: 1, position: "relative" }}>
          <MapView
            horizon={horizon}
            theme={theme}
            onDistrictSelect={openDistrict}
          />
        </main>
      </div>

      {/* ── 경보 오버레이 ── */}
      {alertsOpen && (
        <div onClick={() => setAlertsOpen(false)}
          className="anim-fadeup"
          style={{ position: "fixed", inset: 0, zIndex: 2000,
                   background: "rgba(20,18,15,.45)", backdropFilter: "blur(3px)",
                   display: "flex", justifyContent: "flex-end" }}>
          <div onClick={e => e.stopPropagation()}
            style={{ width: 420, maxWidth: "100%", height: "100%", background: c.bg,
                     overflowY: "auto", boxShadow: "-8px 0 32px rgba(0,0,0,.18)" }}>

            {/* 오버레이 헤더 */}
            <div style={{ position: "sticky", top: 0, background: c.surface,
                          borderBottom: `1px solid ${c.border2}`, padding: "16px 20px",
                          display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <span style={{ fontSize: 18 }}>🚨</span>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 800 }}>경보 알림</div>
                  <div style={{ fontSize: 11.5, color: c.text3, fontWeight: 500 }}>실시간 침수 위험 경보</div>
                </div>
              </div>
              <button onClick={() => setAlertsOpen(false)}
                style={{ width: 32, height: 32, border: `1px solid ${c.border}`, background: c.surface2,
                         borderRadius: 9, cursor: "pointer", color: c.text2, fontSize: 18,
                         display: "flex", alignItems: "center", justifyContent: "center" }}>
                ×
              </button>
            </div>

            <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 10 }}>
              {/* 요약 배너 */}
              <div style={{ borderRadius: 14, padding: 18, color: "#fff",
                            background: `linear-gradient(150deg,${c.danger},#b5281f)`,
                            boxShadow: `0 10px 28px ${c.danger}44` }}>
                <div style={{ fontSize: 11.5, fontWeight: 700, opacity: .9 }}>⚠ 긴급 경보 발령 중</div>
                <div style={{ fontSize: 24, fontWeight: 800, margin: "6px 0 3px" }}>
                  위험·경보 {alertCount}개 지구
                </div>
                <div style={{ fontSize: 12.5, fontWeight: 500, opacity: .9, lineHeight: 1.5 }}>
                  집중호우로 다음 지구의 강수량이 하수도 용량을 초과합니다.
                </div>
              </div>

              {alertDistricts.map(d => {
                const disp = getDisp(d);
                const gs   = gradeStyle(c, disp.grade);
                const over = (disp.rainfall - d.drainage_capacity).toFixed(1);
                return (
                  <button key={d.id} onClick={() => { openDistrict(d); setAlertsOpen(false); }}
                    style={{ textAlign: "left", border: `1px solid ${c.border}`,
                             borderLeft: `3px solid ${gs.color}`, background: c.surface,
                             borderRadius: 12, padding: 14, cursor: "pointer", fontFamily: "inherit",
                             display: "flex", flexDirection: "column", gap: 5,
                             boxShadow: c.elev }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                        <span style={{ fontSize: 11, fontWeight: 800, padding: "2px 8px",
                                       borderRadius: 6, color: gs.color, background: gs.bg }}>
                          {disp.grade}
                        </span>
                        <span style={{ fontSize: 14, fontWeight: 700 }}>{d.name}</span>
                        <span style={{ fontSize: 12, color: c.text3, fontWeight: 500 }}>{d.gu}</span>
                      </div>
                    </div>
                    <div style={{ fontSize: 12.5, color: c.text2, fontWeight: 500, lineHeight: 1.5 }}>
                      강수 {disp.rainfall}mm/hr · 용량 {d.drainage_capacity}mm/hr (+{over}mm 초과)
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

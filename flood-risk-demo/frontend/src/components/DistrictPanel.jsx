import React, { useState } from "react";
import { useTheme, gradeStyle } from "../ThemeContext.jsx";

const GRADE_ORDER = { 위험: 0, 경보: 1, 주의: 2, 안전: 3 };

export default function DistrictPanel({ districts, horizon, getDisp, onDistrictClick, onLocationClick }) {
  const { c } = useTheme();
  const [cityFilter, setCity] = useState("전체");

  const cities = ["전체", ...new Set(districts.map(d => d.city))];

  const counts = { 위험: 0, 경보: 0, 주의: 0, 안전: 0 };
  districts.forEach(d => { const g = getDisp(d).grade; if (counts[g] !== undefined) counts[g]++; });
  const vulnCount = counts["위험"] + counts["경보"];

  const visible = districts
    .filter(d => cityFilter === "전체" || d.city === cityFilter)
    .sort((a, b) => (GRADE_ORDER[getDisp(a).grade] ?? 4) - (GRADE_ORDER[getDisp(b).grade] ?? 4));

  const GRADE_COLORS = {
    안전: c.safe, 주의: c.caution, 경보: c.alert, 위험: c.danger,
  };
  const GRADE_SOFT = {
    안전: c.safeSoft, 주의: c.cautionSoft, 경보: c.alertSoft, 위험: c.dangerSoft,
  };

  return (
    <div className="anim-slidein">
      {/* 내 위치 */}
      <div style={{ padding: "16px 18px 10px" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: c.text2 }}>내 위치 위험도</div>
          <button onClick={onLocationClick}
            style={{ display: "flex", alignItems: "center", gap: 5, height: 30, padding: "0 11px",
                     border: `1px solid ${c.primary}`, color: c.primary, background: c.primarySoft,
                     borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: "pointer", fontFamily: "inherit" }}>
            ◎ 내 위치
          </button>
        </div>
        <button onClick={onLocationClick}
          style={{ width: "100%", textAlign: "left", border: `1px dashed ${c.border}`,
                   background: c.surface2, borderRadius: 13, padding: 18,
                   display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                   cursor: "pointer", fontFamily: "inherit" }}>
          <div style={{ width: 42, height: 42, borderRadius: "50%", background: c.primarySoft,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        color: c.primary, fontSize: 18 }}>◎</div>
          <div style={{ textAlign: "center", fontSize: 13, color: c.text2, lineHeight: 1.5, fontWeight: 500 }}>
            버튼을 눌러 현재 위치의<br />침수 위험도를 확인하세요
          </div>
        </button>
      </div>

      {/* 취약 지구 목록 */}
      <div style={{ padding: "12px 18px 6px", borderTop: `1px solid ${c.border2}`, marginTop: 4 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: c.text2 }}>침수 취약 지구</div>
          {vulnCount > 0 && (
            <div style={{ fontSize: 12, fontWeight: 700, color: c.danger, background: c.dangerSoft,
                          padding: "3px 9px", borderRadius: 20 }}>
              ⚠ {vulnCount}곳
            </div>
          )}
        </div>

        {/* 등급 카드 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8, marginBottom: 12 }}>
          {["위험","경보","주의","안전"].map(g => (
            <div key={g} style={{ border: `1px solid ${c.border}`, borderRadius: 10,
                                  padding: "10px 8px", textAlign: "center" }}>
              <div className="mono" style={{ fontSize: 20, fontWeight: 700, color: GRADE_COLORS[g] }}>
                {counts[g]}
              </div>
              <div style={{ fontSize: 11, color: c.text3, marginTop: 1, fontWeight: 600 }}>{g}</div>
            </div>
          ))}
        </div>

        {/* 도시 필터 */}
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 4 }}>
          {cities.map(city => (
            <button key={city} onClick={() => setCity(city)}
              style={{ height: 28, padding: "0 12px", borderRadius: 20, fontSize: 12,
                       fontWeight: 700, cursor: "pointer", fontFamily: "inherit",
                       border: `1px solid ${cityFilter === city ? c.primary : c.border}`,
                       background: cityFilter === city ? c.primary : c.surface,
                       color: cityFilter === city ? "#fff" : c.text2 }}>
              {city}
            </button>
          ))}
        </div>
      </div>

      {/* 지구 목록 */}
      <div style={{ padding: "8px 18px 18px", display: "flex", flexDirection: "column", gap: 9 }}>
        {visible.length === 0 && (
          <div style={{ padding: "32px 12px", textAlign: "center", color: c.text3, fontSize: 13 }}>
            해당 지역의 모니터링 지구가 없습니다
          </div>
        )}
        {visible.map(d => {
          const disp  = getDisp(d);
          const gs    = gradeStyle(c, disp.grade);
          const rain  = disp.rainfall;
          const cap   = d.drainage_capacity;
          const pct   = Math.min(rain / Math.max(cap, 1) * 100, 100);
          const over  = rain - cap;

          return (
            <button key={d.id} onClick={() => onDistrictClick(d)}
              style={{ textAlign: "left", border: `1px solid ${c.border}`, background: c.surface,
                       borderRadius: 13, padding: 13, cursor: "pointer", fontFamily: "inherit",
                       display: "flex", flexDirection: "column", gap: 8, boxShadow: c.elev }}>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7, minWidth: 0 }}>
                  <span style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: gs.color }} />
                  <span style={{ fontSize: 15, fontWeight: 700, letterSpacing: "-.01em" }}>{d.name}</span>
                  <span style={{ fontSize: 12, color: c.text3, fontWeight: 500 }}>{d.gu}</span>
                </div>
                <span style={{ fontSize: 11, fontWeight: 800, padding: "2px 8px", borderRadius: 6,
                               flexShrink: 0, color: gs.color, background: gs.bg }}>
                  {disp.grade}
                </span>
              </div>

              {/* 게이지 바 */}
              <div style={{ height: 6, borderRadius: 4, background: c.border2, overflow: "hidden" }}>
                <div className="bar-fill"
                     style={{ height: "100%", borderRadius: 4, width: `${pct}%`, background: gs.color }} />
              </div>

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span className="mono" style={{ fontSize: 12.5, color: c.text2, fontWeight: 500 }}>
                  {rain}mm / {cap}mm
                </span>
                <span style={{ fontSize: 12.5, fontWeight: 700,
                               color: over >= 0 ? c.danger : c.safe }}>
                  {over >= 0 ? `+${over.toFixed(1)}mm 초과` : `여유 ${(-over).toFixed(1)}mm`}
                </span>
              </div>

              {d.flood_history >= 0.8 && (
                <div style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11.5, color: c.alert, fontWeight: 600 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: c.alert }} />
                  과거 침수 이력 높음
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

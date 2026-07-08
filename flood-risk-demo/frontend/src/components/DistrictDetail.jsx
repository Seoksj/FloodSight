import React from "react";
import { useTheme, gradeStyle } from "../ThemeContext.jsx";

const HORIZON_LABEL = { current: "현재", "1h": "1시간 후", "3h": "3시간 후" };

export default function DistrictDetail({ district: d, horizon, getDisp, onBack }) {
  const { c } = useTheme();
  const disp = getDisp(d);
  const gs   = gradeStyle(c, disp.grade);
  const rain = disp.rainfall;
  const cap  = d.drainage_capacity;
  const pct  = Math.min(rain / Math.max(cap, 1) * 100, 100);
  const over = rain - cap;

  // 예보 바 차트 데이터
  const forecastBars = [
    { label: "현재",     rain: d.rainfall_1h,                grade: d.grade },
    { label: "1시간 후", rain: d.forecast?.["1h"]?.rainfall ?? d.rainfall_1h * 1.1, grade: d.forecast?.["1h"]?.grade ?? d.grade },
    { label: "3시간 후", rain: d.forecast?.["3h"]?.rainfall ?? d.rainfall_1h * 1.2, grade: d.forecast?.["3h"]?.grade ?? d.grade },
  ];
  const maxRain = Math.max(...forecastBars.map(f => f.rain), cap) * 1.1;

  const barColor = (grade) => gradeStyle(c, grade).color;

  return (
    <div className="anim-slidein">
      {/* 헤더 */}
      <div style={{ padding: "14px 18px", borderBottom: `1px solid ${c.border2}`,
                    display: "flex", alignItems: "center", gap: 10 }}>
        <button onClick={onBack}
          style={{ width: 32, height: 32, border: `1px solid ${c.border}`, background: c.surface2,
                   borderRadius: 9, cursor: "pointer", color: c.text2, fontSize: 16,
                   display: "flex", alignItems: "center", justifyContent: "center" }}>
          ←
        </button>
        <div style={{ fontSize: 13, fontWeight: 700, color: c.text2 }}>지구 상세</div>
      </div>

      <div style={{ padding: "18px 18px 24px" }}>
        {/* 제목 */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between",
                      gap: 10, marginBottom: 6 }}>
          <div>
            <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-.02em" }}>{d.name}</div>
            <div style={{ fontSize: 13, color: c.text3, fontWeight: 500, marginTop: 2 }}>
              {d.gu} · {d.city}
              {horizon !== "current" && (
                <span style={{ color: c.primary, marginLeft: 6 }}>· {HORIZON_LABEL[horizon]}</span>
              )}
            </div>
          </div>
          <span style={{ fontSize: 13, fontWeight: 800, padding: "5px 12px", borderRadius: 9,
                         color: gs.color, background: gs.bg, flexShrink: 0 }}>
            {disp.grade}
          </span>
        </div>

        {/* 강수량 카드 */}
        <div style={{ border: `1px solid ${c.border}`, borderRadius: 13, padding: 16,
                      marginTop: 14, background: c.surface2 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
            <span className="mono" style={{ fontSize: 38, fontWeight: 700, color: gs.color, lineHeight: 1 }}>
              {rain.toFixed(1)}
            </span>
            <span style={{ fontSize: 14, color: c.text3, fontWeight: 600 }}>mm</span>
            <span style={{ marginLeft: "auto", fontSize: 13, fontWeight: 700,
                           color: over >= 0 ? c.danger : c.safe }}>
              {over >= 0 ? `+${over.toFixed(1)}mm 초과` : `여유 ${(-over).toFixed(1)}mm`}
            </span>
          </div>
          <div style={{ fontSize: 12, color: c.text2, marginTop: 5, fontWeight: 500 }}>
            시간당 강수량 · 하수도 용량 {cap}mm/hr
          </div>
          <div style={{ position: "relative", height: 8, borderRadius: 5,
                        background: c.border2, overflow: "hidden", marginTop: 12 }}>
            <div className="bar-fill"
                 style={{ height: "100%", borderRadius: 5, width: `${pct}%`, background: gs.color }} />
          </div>
        </div>

        {/* 예보 바 차트 */}
        <div style={{ fontSize: 13, fontWeight: 700, color: c.text2, margin: "20px 0 12px" }}>
          시간대별 예측 강수량
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "flex-end", height: 130 }}>
          {forecastBars.map(f => {
            const fColor = barColor(f.grade);
            const h = Math.max(f.rain / maxRain * 100, 6);
            return (
              <div key={f.label} style={{ flex: 1, display: "flex", flexDirection: "column",
                                          alignItems: "center", gap: 7, height: "100%",
                                          justifyContent: "flex-end" }}>
                <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: fColor }}>
                  {f.rain.toFixed(0)}
                </span>
                <div style={{ width: "100%", background: c.border2, borderRadius: "7px 7px 0 0",
                              height: `${h}%`, overflow: "hidden" }}>
                  <div style={{ width: "100%", height: "100%", background: fColor,
                                borderRadius: "7px 7px 0 0", opacity: .9 }} />
                </div>
                <span style={{ fontSize: 11.5, color: c.text3, fontWeight: 600 }}>{f.label}</span>
              </div>
            );
          })}
        </div>

        {/* 침수 이력 */}
        {d.flood_history >= 0.6 && (
          <div style={{ marginTop: 22, border: `1px solid ${c.alert}`, background: c.alertSoft,
                        borderRadius: 13, padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13,
                          fontWeight: 700, color: c.alert, marginBottom: 6 }}>
              ⚠ 과거 침수 이력
            </div>
            <div style={{ fontSize: 13, color: c.text2, fontWeight: 500, lineHeight: 1.5 }}>
              침수 이력 지수 {Math.round(d.flood_history * 100)}점 — 반복 침수 위험 지구입니다.
            </div>
          </div>
        )}

        {/* 판단 근거 */}
        {d.reason && (
          <div style={{ marginTop: 18, fontSize: 13, color: c.text2, lineHeight: 1.7,
                        padding: 14, background: c.surface2, borderRadius: 11,
                        border: `1px solid ${c.border}` }}>
            {d.reason}
          </div>
        )}

      </div>
    </div>
  );
}

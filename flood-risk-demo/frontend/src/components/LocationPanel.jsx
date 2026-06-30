import React, { useState, useCallback } from "react";
import { useTheme, gradeStyle } from "../ThemeContext.jsx";
import { apiFetch } from "../api.js";

const TIPS = [
  "지하 주차장·반지하 등 저지대 장소는 즉시 대피하세요.",
  "하천변·지하차도 통행을 삼가고 우회로를 이용하세요.",
  "강수 강도가 높아지면 가까운 대피소로 이동하세요.",
];

export default function LocationPanel({ onBack, onDistrictClick }) {
  const { c } = useTheme();
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [result,   setResult]   = useState(null);

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
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          setResult({ ...(await res.json()), lat, lon });
        } catch (e) { setError(e.message); }
        finally { setLoading(false); }
      },
      (e) => { setError(`위치 오류: ${e.message}`); setLoading(false); },
      { timeout: 10000 }
    );
  }, []);

  const gs = result ? gradeStyle(c, result.grade) : null;

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
        <div style={{ fontSize: 13, fontWeight: 700, color: c.text2 }}>내 위치 위험도</div>
      </div>

      {/* 로딩 */}
      {loading && (
        <div style={{ padding: "60px 24px", textAlign: "center" }}>
          <div className="anim-spin"
               style={{ width: 44, height: 44, borderRadius: "50%",
                        border: `3px solid ${c.border}`, borderTopColor: c.primary,
                        margin: "0 auto 16px" }} />
          <div style={{ fontSize: 14, color: c.text2, fontWeight: 600 }}>현재 위치를 확인하는 중...</div>
        </div>
      )}

      {/* 오류 */}
      {error && !loading && (
        <div style={{ margin: "16px 18px", padding: "12px 14px", borderRadius: 10,
                      background: c.dangerSoft, color: c.danger, fontSize: 13,
                      border: `1px solid ${c.danger}44` }}>
          {error}
        </div>
      )}

      {/* 결과 */}
      {result && gs && !loading && (
        <div style={{ padding: "18px 18px 24px" }}>
          <div style={{ fontSize: 12, color: c.text3, fontWeight: 600, marginBottom: 3 }}>◎ 현재 위치</div>
          <div style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.02em" }}>
            {result.nearest_district?.city} {result.nearest_district?.gu}
          </div>
          <div className="mono" style={{ fontSize: 12, color: c.text3, marginTop: 2 }}>
            {result.lat?.toFixed(4)}, {result.lon?.toFixed(4)}
          </div>

          {/* 위험 등급 카드 */}
          <div style={{ marginTop: 16, borderRadius: 15, padding: 20, textAlign: "center",
                        color: "#fff",
                        background: `linear-gradient(150deg,${gs.color},${gs.color}cc)`,
                        boxShadow: `0 8px 24px ${gs.color}44` }}>
            <div style={{ fontSize: 12.5, fontWeight: 700, opacity: .9 }}>현재 침수 위험 단계</div>
            <div style={{ fontSize: 32, fontWeight: 800, margin: "5px 0 2px", letterSpacing: "-.01em" }}>
              {result.grade}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, opacity: .9 }}>
              위험 점수 {Math.round(result.risk_score * 100)}점
            </div>
          </div>

          {/* 수치 그리드 */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 9, marginTop: 12 }}>
            <div style={{ border: `1px solid ${c.border}`, borderRadius: 12, padding: 13 }}>
              <div style={{ fontSize: 11, color: c.text3, fontWeight: 600 }}>현재 강수량</div>
              <div className="mono" style={{ fontSize: 20, fontWeight: 700, marginTop: 2 }}>
                {result.rainfall_1h}
                <span style={{ fontSize: 12, color: c.text3 }}> mm</span>
              </div>
            </div>
            <div style={{ border: `1px solid ${c.border}`, borderRadius: 12, padding: 13 }}>
              <div style={{ fontSize: 11, color: c.text3, fontWeight: 600 }}>하수도 여유</div>
              <div className="mono"
                   style={{ fontSize: 20, fontWeight: 700, marginTop: 2, color: gs.color }}>
                {result.rainfall_1h > result.drainage_capacity
                  ? `+${(result.rainfall_1h - result.drainage_capacity).toFixed(1)}`
                  : (result.drainage_capacity - result.rainfall_1h).toFixed(1)}
                <span style={{ fontSize: 12, color: c.text3 }}> mm</span>
              </div>
            </div>
          </div>

          {/* 가장 가까운 위험 지구 */}
          {result.nearest_district && (
            <button onClick={() => onDistrictClick?.(result.nearest_district)}
              style={{ width: "100%", marginTop: 10, border: `1px solid ${c.border}`,
                       borderRadius: 12, padding: "12px 13px", display: "flex", alignItems: "center",
                       gap: 11, background: c.surface, cursor: "pointer", fontFamily: "inherit",
                       textAlign: "left" }}>
              <div style={{ width: 36, height: 36, borderRadius: 9, background: c.dangerSoft,
                            color: c.danger, display: "flex", alignItems: "center",
                            justifyContent: "center", fontSize: 15, flexShrink: 0 }}>
                ⚠
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>가장 가까운 위험 지구</div>
                <div style={{ fontSize: 12.5, color: c.text2, fontWeight: 500, marginTop: 1 }}>
                  {result.nearest_district.name} · {result.nearest_district.distance_km}km
                </div>
              </div>
            </button>
          )}

          {/* 행동 요령 */}
          <div style={{ fontSize: 13, fontWeight: 700, color: c.text2, margin: "18px 0 10px" }}>
            행동 요령
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {TIPS.map((tip, i) => (
              <div key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start",
                                    border: `1px solid ${c.border}`, borderRadius: 11,
                                    padding: "11px 13px" }}>
                <span style={{ color: c.primary, fontWeight: 800, fontSize: 13, marginTop: 1 }}>
                  {i + 1}
                </span>
                <span style={{ fontSize: 13, color: c.text, lineHeight: 1.5, fontWeight: 500 }}>
                  {tip}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 초기 상태 */}
      {!result && !loading && !error && (
        <div style={{ padding: "24px 18px" }}>
          <button onClick={detect}
            style={{ width: "100%", border: `1px solid ${c.primary}`, color: c.primary,
                     background: c.primarySoft, borderRadius: 13, padding: 20,
                     display: "flex", flexDirection: "column", alignItems: "center", gap: 9,
                     cursor: "pointer", fontFamily: "inherit" }}>
            <div style={{ width: 44, height: 44, borderRadius: "50%", background: c.primary,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          color: "#fff", fontSize: 20 }}>
              ◎
            </div>
            <div style={{ fontSize: 14, fontWeight: 700 }}>내 위치 확인</div>
            <div style={{ fontSize: 12.5, color: c.text2, lineHeight: 1.5 }}>
              GPS로 현재 위치의 침수 위험도를 조회합니다
            </div>
          </button>
        </div>
      )}
    </div>
  );
}

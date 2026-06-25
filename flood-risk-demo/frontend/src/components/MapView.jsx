import React, { useEffect, useRef, useState, useCallback } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTheme } from "../ThemeContext.jsx";
import { apiFetch } from "../api.js";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const GRADE_CFG = {
  안전: { color: "#22c55e" },
  주의: { color: "#eab308" },
  경보: { color: "#f97316" },
  위험: { color: "#ef4444" },
};
const HORIZON_LABEL = { current: "현재", "1h": "1시간 후", "3h": "3시간 후" };

function DistrictLayer({ geojson, onSelect }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (!geojson || !map) return;
    layerRef.current?.remove();

    const layer = L.geoJSON(geojson, {
      style: (f) => ({
        fillColor:   f.properties.color,
        fillOpacity: f.properties.opacity,
        color:       f.properties.color,
        weight:      1,
        opacity:     0.4,
      }),
      onEachFeature: (feature, lyr) => {
        const p = feature.properties;
        const gradeColor = GRADE_CFG[p.grade]?.color ?? "#fff";
        lyr.bindTooltip(
          `<div style="line-height:1.6">
             <b style="color:#fff">${p.city} ${p.gu} ${p.name}</b><br>
             <span style="color:${gradeColor};font-weight:600">${p.grade}</span>
             <span style="color:#64748b;margin-left:6px">${(p.risk_score*100).toFixed(0)}점</span><br>
             <span style="color:#475569">강수 ${p.rainfall_1h}mm/hr · 용량 ${p.drainage_capacity}mm/hr</span>
           </div>`,
          { sticky: true, className: "flood-tooltip" }
        );
        lyr.on("click", () => onSelect && onSelect(p));
        lyr.on("mouseover", () => lyr.setStyle({ weight: 2, opacity: 0.8, fillOpacity: Math.min(f.properties.opacity + 0.15, 0.95) }));
        lyr.on("mouseout",  () => layer.resetStyle(lyr));
      },
    }).addTo(map);

    layerRef.current = layer;
    return () => layer.remove();
  }, [geojson, map, onSelect]);

  return null;
}

export default function MapView({ horizon = "current", onDistrictSelect }) {
  const { c } = useTheme();
  const [geojson,   setGeojson]   = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [lastFetch, setLastFetch] = useState(null);
  const [selected,  setSelected]  = useState(null);

  const fetchRisk = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/risk?horizon=${horizon}`);
      if (res.ok) { setGeojson(await res.json()); setLastFetch(new Date()); }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [horizon]);

  useEffect(() => {
    fetchRisk();
    const id = setInterval(fetchRisk, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchRisk]);

  useEffect(() => { setSelected(null); }, [horizon]);

  const handleSelect = useCallback((props) => {
    setSelected(props);
    onDistrictSelect?.(props);
  }, [onDistrictSelect]);

  const cfg    = selected ? (GRADE_CFG[selected.grade] ?? GRADE_CFG["안전"]) : null;
  const overMm = selected ? Math.round((selected.rainfall_1h - selected.drainage_capacity) * 10) / 10 : 0;
  const isOver = selected && selected.rainfall_1h > selected.drainage_capacity;
  const scorePct = selected ? Math.min(selected.risk_score * 100, 100) : 0;

  return (
    <div className="relative w-full h-full">
      {loading && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] text-xs px-3 py-1.5 rounded-full font-medium"
             style={{ background: "rgba(37,99,235,0.9)", color: "#fff",
                      backdropFilter: "blur(8px)", boxShadow: "0 4px 12px rgba(37,99,235,0.4)" }}>
          지도 갱신 중...
        </div>
      )}

      {/* 선택 팝업 */}
      {selected && cfg && (
        <div className="absolute top-4 right-4 z-[1000] w-[260px] rounded-2xl"
             style={{ background: c.bgOverlay, border: `1px solid ${c.borderMid}`,
                      backdropFilter: "blur(16px)", boxShadow: "0 20px 40px rgba(0,0,0,0.25)", padding: "16px" }}>
          <div className="flex items-start justify-between mb-3">
            <div>
              <div className="text-sm font-bold" style={{ color: c.textPrimary }}>{selected.name}</div>
              <div className="text-xs mt-0.5" style={{ color: c.textMuted }}>
                {selected.city} {selected.gu}
                {horizon !== "current" && (
                  <span style={{ color: c.pillText, marginLeft: 6 }}>· {HORIZON_LABEL[horizon]}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold px-2 py-1 rounded-lg"
                    style={{ background: `${cfg.color}22`, color: cfg.color, border: `1px solid ${cfg.color}44` }}>
                {selected.grade}
              </span>
              <button onClick={() => setSelected(null)}
                className="w-6 h-6 rounded-md flex items-center justify-center text-lg leading-none transition-colors"
                style={{ color: c.textFaint, background: c.bgInput }}>
                ×
              </button>
            </div>
          </div>

          {/* 점수 게이지 */}
          <div className="mb-3">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-[11px]" style={{ color: c.textMuted }}>위험 점수</span>
              <span className="text-sm font-bold" style={{ color: cfg.color }}>
                {Math.round(selected.risk_score * 100)}점
              </span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: c.border }}>
              <div className="h-full rounded-full gauge-bar"
                   style={{ width: `${scorePct}%`, background: cfg.color, boxShadow: `0 0 8px ${cfg.color}66` }} />
            </div>
          </div>

          {/* 수치 그리드 */}
          <div className="grid grid-cols-2 gap-1.5 mb-3">
            {[
              { label: "강수량",     value: `${selected.rainfall_1h}mm/hr` },
              { label: "하수도 용량", value: `${selected.drainage_capacity}mm/hr` },
              {
                label: "배수 상태",
                value: isOver ? `+${overMm}mm 초과` : `여유 ${Math.abs(overMm)}mm`,
                color: isOver ? "#f87171" : "#4ade80",
              },
              {
                label: "불투수율",
                value: `${Math.round((selected.impervious_ratio ?? 0) * 100)}%`,
              },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-lg px-2.5 py-2"
                   style={{ background: c.bgNum, border: `1px solid ${c.border}` }}>
                <div className="text-[10px] mb-0.5" style={{ color: c.textFaint }}>{label}</div>
                <div className="text-xs font-semibold" style={{ color: color || c.textPrimary }}>{value}</div>
              </div>
            ))}
          </div>

          <p className="text-[11px] leading-relaxed" style={{ color: c.textMuted }}>{selected.reason}</p>
        </div>
      )}

      {lastFetch && (
        <div className="absolute bottom-8 left-3 z-[1000] text-[11px] px-2.5 py-1 rounded-lg"
             style={{ background: c.mapBg, color: c.textMuted,
                      backdropFilter: "blur(8px)", border: `1px solid ${c.border}` }}>
          {lastFetch.toLocaleTimeString("ko-KR")} 기준
        </div>
      )}

      <MapContainer center={[36.5, 127.8]} zoom={7} className="w-full h-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {geojson && <DistrictLayer geojson={geojson} onSelect={handleSelect} />}
      </MapContainer>
    </div>
  );
}

import React, { useEffect, useRef, useCallback, useState } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useTheme, gradeStyle } from "../ThemeContext.jsx";
import { apiFetch } from "../api.js";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconUrl:       "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl:     "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN ?? "";

function TileLayerSwitch({ theme }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (!map) return;
    if (layerRef.current) layerRef.current.remove();
    const style = theme === "dark" ? "dark-v11" : "streets-v12";
    const url = `https://api.mapbox.com/styles/v1/mapbox/${style}/tiles/{z}/{x}/{y}?access_token=${MAPBOX_TOKEN}`;
    layerRef.current = L.tileLayer(url, {
      attribution: '© <a href="https://www.mapbox.com/">Mapbox</a> © <a href="https://www.openstreetmap.org/">OpenStreetMap</a>',
      tileSize: 512,
      zoomOffset: -1,
      maxZoom: 22,
    }).addTo(map);
    return () => layerRef.current?.remove();
  }, [theme, map]);

  return null;
}

const GRADE_ICON = {
  "안전": { emoji: "✅", bg: "#4CAF50", shadow: "#4CAF5055" },
  "주의": { emoji: "⚠️", bg: "#FFC107", shadow: "#FFC10755" },
  "경보": { emoji: "🔶", bg: "#FF9800", shadow: "#FF980055" },
  "위험": { emoji: "🚨", bg: "#F44336", shadow: "#F4433655" },
};

function makeGradeIcon(grade, name) {
  const g = GRADE_ICON[grade] ?? GRADE_ICON["안전"];
  return L.divIcon({
    className: "",
    iconAnchor: [60, 60],
    html: `
      <div style="
        display:flex; flex-direction:column; align-items:center; gap:4px;
        filter: drop-shadow(0 3px 8px ${g.shadow});
      ">
        <div style="
          width:48px; height:48px; border-radius:50%;
          background:${g.bg}; border:3px solid #fff;
          display:flex; align-items:center; justify-content:center;
          font-size:22px; box-shadow:0 2px 12px ${g.shadow};
        ">${g.emoji}</div>
        <div style="
          background:rgba(0,0,0,0.72); color:#fff;
          font-size:11px; font-weight:700; padding:3px 8px;
          border-radius:8px; white-space:nowrap; letter-spacing:-.01em;
        ">${name} · ${grade}</div>
      </div>`,
  });
}

function DistrictLayer({ geojson, onSelect }) {
  const { c } = useTheme();
  const map = useMap();
  const layerRef    = useRef(null);
  const selectedRef = useRef(null);
  const markerRef   = useRef(null);

  useEffect(() => {
    if (!geojson || !map) return;
    layerRef.current?.remove();
    markerRef.current?.remove();
    selectedRef.current = null;

    const layer = L.geoJSON(geojson, {
      style: f => ({
        fillColor:   f.properties.color,
        fillOpacity: f.properties.opacity ?? 0.42,
        color:       f.properties.color,
        weight:      1.5,
        opacity:     0.55,
      }),
      onEachFeature: (feature, lyr) => {
        const p = feature.properties;
        lyr.bindTooltip(
          `<b>${p.name}</b> · ${p.grade}`,
          { sticky: true, className: "fs-tooltip", direction: "top" }
        );
        lyr.on("click", (e) => {
          // 이전 선택 해제
          if (selectedRef.current && selectedRef.current !== lyr) {
            layer.resetStyle(selectedRef.current);
          }
          // 경계 강조
          lyr.setStyle({
            weight:      4,
            color:       "#ffffff",
            opacity:     1,
            fillOpacity: Math.min((p.opacity ?? 0.42) + 0.25, 0.92),
          });
          lyr.bringToFront();
          selectedRef.current = lyr;

          // 기존 아이콘 마커 제거 후 중심점에 새로 추가
          markerRef.current?.remove();
          const center = lyr.getBounds().getCenter();
          markerRef.current = L.marker(center, {
            icon: makeGradeIcon(p.grade, p.name),
            interactive: false,
          }).addTo(map);

          onSelect?.(p);
        });
        lyr.on("mouseover", () => {
          if (selectedRef.current === lyr) return;
          lyr.setStyle({ weight: 2.5, fillOpacity: Math.min((p.opacity ?? 0.42) + 0.18, 0.9) });
        });
        lyr.on("mouseout", () => {
          if (selectedRef.current === lyr) return;
          layer.resetStyle(lyr);
        });
      },
    }).addTo(map);

    layerRef.current = layer;
    return () => { layer.remove(); markerRef.current?.remove(); };
  }, [geojson, map, onSelect, c]);

  return null;
}

export default function MapView({ horizon = "current", theme, onDistrictSelect }) {
  const { c } = useTheme();
  const [geojson,   setGeojson]   = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [lastFetch, setLastFetch] = useState(null);

  const fetchRisk = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiFetch(`/api/risk?horizon=${horizon}`);
      if (res.ok) { setGeojson(await res.json()); setLastFetch(new Date()); }
    } catch {}
    finally { setLoading(false); }
  }, [horizon]);

  useEffect(() => {
    fetchRisk();
    const id = setInterval(fetchRisk, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, [fetchRisk]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      {loading && (
        <div style={{ position: "absolute", top: 14, left: "50%", transform: "translateX(-50%)",
                      zIndex: 1000, background: c.primary, color: "#fff", borderRadius: 20,
                      padding: "5px 14px", fontSize: 12, fontWeight: 600,
                      boxShadow: `0 4px 12px ${c.primary}55` }}>
          갱신 중…
        </div>
      )}

      {lastFetch && (
        <div style={{ position: "absolute", left: 12, bottom: 12, zIndex: 500,
                      background: c.surface, border: `1px solid ${c.border}`,
                      borderRadius: 9, padding: "7px 12px",
                      display: "flex", alignItems: "center", gap: 7,
                      boxShadow: c.elev, pointerEvents: "none" }}>
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: c.safe,
                         boxShadow: `0 0 0 3px ${c.safeSoft}` }} />
          <span className="mono" style={{ fontSize: 12, fontWeight: 600, color: c.text2 }}>
            {lastFetch.toLocaleTimeString("ko-KR")} 기준
          </span>
        </div>
      )}

      <MapContainer
        center={[37.52, 126.65]} zoom={10}
        minZoom={9} maxZoom={18}
        maxBounds={[[37.00, 125.80], [37.95, 127.80]]}
        maxBoundsViscosity={0.85}
        style={{ position: "absolute", inset: 0, background: c.bg }}
        zoomControl={true}>
        <TileLayerSwitch theme={theme} />
        {geojson && <DistrictLayer geojson={geojson} onSelect={onDistrictSelect} />}
      </MapContainer>
    </div>
  );
}

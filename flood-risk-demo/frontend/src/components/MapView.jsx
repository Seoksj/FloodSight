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

function TileLayerSwitch({ theme }) {
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (!map) return;
    if (layerRef.current) layerRef.current.remove();
    const url = theme === "dark"
      ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";
    layerRef.current = L.tileLayer(url, {
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com">CARTO</a>',
      maxZoom: 19,
    }).addTo(map);
    return () => layerRef.current?.remove();
  }, [theme, map]);

  return null;
}

function DistrictLayer({ geojson, onSelect }) {
  const { c } = useTheme();
  const map = useMap();
  const layerRef = useRef(null);

  useEffect(() => {
    if (!geojson || !map) return;
    layerRef.current?.remove();

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
        lyr.on("click",    () => onSelect?.(p));
        lyr.on("mouseover", () => lyr.setStyle({ weight: 2.5, fillOpacity: Math.min((f.properties.opacity ?? 0.42) + 0.18, 0.9) }));
        lyr.on("mouseout",  () => layer.resetStyle(lyr));
      },
    }).addTo(map);

    layerRef.current = layer;
    return () => layer.remove();
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

      <MapContainer center={[37.555, 126.99]} zoom={11}
        style={{ position: "absolute", inset: 0, background: c.bg }}
        zoomControl={true}>
        <TileLayerSwitch theme={theme} />
        {geojson && <DistrictLayer geojson={geojson} onSelect={onDistrictSelect} />}
      </MapContainer>
    </div>
  );
}

import React, { useEffect, useState } from "react";

const GRADE_COLOR = {
  안전: { bar: "bg-green-500",  badge: "bg-green-900 text-green-400 border-green-700" },
  주의: { bar: "bg-yellow-500", badge: "bg-yellow-900 text-yellow-400 border-yellow-700" },
  경보: { bar: "bg-orange-500", badge: "bg-orange-900 text-orange-400 border-orange-700" },
  위험: { bar: "bg-red-500",    badge: "bg-red-900 text-red-400 border-red-700" },
};

function ProgressBar({ pct, grade }) {
  const color = GRADE_COLOR[grade]?.bar ?? "bg-gray-500";
  const width  = Math.min(pct, 100);
  return (
    <div className="relative w-full bg-gray-700 rounded-full h-1.5 overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-500 ${color}`}
        style={{ width: `${width}%` }}
      />
      {pct > 100 && (
        <div className="absolute inset-0 rounded-full animate-pulse bg-red-500/30" />
      )}
    </div>
  );
}

function GradeBadge({ grade }) {
  const cls = GRADE_COLOR[grade]?.badge ?? "bg-gray-800 text-gray-400 border-gray-600";
  return (
    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${cls}`}>
      {grade}
    </span>
  );
}

export default function StationPanel() {
  const [stations, setStations] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);

  const fetchStations = async () => {
    try {
      const res = await fetch("/api/stations");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setStations(data.stations ?? []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStations();
    const id = setInterval(fetchStations, 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  if (loading) return (
    <div className="flex flex-col gap-2">
      <h2 className="text-sm font-semibold text-gray-300">관측소 현황</h2>
      {[...Array(4)].map((_, i) => (
        <div key={i} className="h-14 bg-gray-800 rounded-lg animate-pulse" />
      ))}
    </div>
  );

  if (error) return (
    <div className="text-xs text-red-400 py-2">{error}</div>
  );

  const alertCount = stations.filter(s => ["경보","위험"].includes(s.grade)).length;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300">관측소 현황</h2>
        {alertCount > 0 && (
          <span className="text-xs bg-red-900 text-red-400 border border-red-700 rounded px-2 py-0.5">
            경보 이상 {alertCount}개소
          </span>
        )}
      </div>

      <div className="flex flex-col gap-1.5 max-h-[calc(100vh-420px)] overflow-y-auto pr-1">
        {stations.map((s) => (
          <div
            key={s.station_id}
            className="bg-gray-800 rounded-lg px-3 py-2.5 border border-gray-700 hover:border-gray-600 transition-colors"
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-sm font-medium text-white">{s.name}</span>
              <GradeBadge grade={s.grade} />
            </div>

            <div className="flex items-center gap-2 text-xs text-gray-400 mb-1.5">
              <span>수위 <b className="text-gray-200">{s.water_level?.toFixed(2)}m</b></span>
              <span className="text-gray-600">/</span>
              <span>기준 {s.alert_level?.toFixed(1)}m</span>
              <span className="ml-auto text-gray-400">
                {s.wl_pct?.toFixed(0)}%
              </span>
            </div>

            <ProgressBar pct={s.wl_pct ?? 0} grade={s.grade} />

            {s.rainfall_1h > 0 && (
              <div className="mt-1 text-xs text-gray-500">
                1h: {s.rainfall_1h?.toFixed(1)}mm  ·  24h: {s.rainfall_24h?.toFixed(1)}mm
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

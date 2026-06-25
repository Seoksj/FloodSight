import React from "react";
import { useTheme } from "../ThemeContext.jsx";

const LEGEND = [
  { grade: "안전", color: "#22c55e" },
  { grade: "주의", color: "#eab308" },
  { grade: "경보", color: "#f97316" },
  { grade: "위험", color: "#ef4444" },
];

export default function LegendBar() {
  const { c } = useTheme();
  return (
    <div className="flex items-center gap-3">
      {LEGEND.map(({ grade, color }) => (
        <div key={grade} className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-sm" style={{ background: color, opacity: 0.9 }} />
          <span className="text-xs" style={{ color: c.textMuted }}>{grade}</span>
        </div>
      ))}
    </div>
  );
}

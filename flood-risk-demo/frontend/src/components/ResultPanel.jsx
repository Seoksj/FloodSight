import React from "react";

const RISK_CONFIG = {
  HIGH:   { label: "고위험",  bg: "bg-red-900",    border: "border-red-500",   text: "text-red-400",   dot: "bg-red-500" },
  MEDIUM: { label: "중위험",  bg: "bg-yellow-900", border: "border-yellow-500", text: "text-yellow-400", dot: "bg-yellow-500" },
  LOW:    { label: "저위험",  bg: "bg-green-900",  border: "border-green-500", text: "text-green-400", dot: "bg-green-500" },
};

function StatCard({ label, value, unit }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1">
      <span className="text-xs text-gray-400">{label}</span>
      <span className="text-xl font-bold text-white">
        {value}
        {unit && <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>}
      </span>
    </div>
  );
}

export default function ResultPanel({ riskLevel, stats }) {
  if (!riskLevel || !stats) {
    return (
      <div className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold text-white">분석 결과</h2>
        <div className="bg-gray-800 rounded-xl p-6 flex items-center justify-center border border-gray-700 h-32">
          <p className="text-gray-500 text-sm">예측 후 결과가 표시됩니다</p>
        </div>
      </div>
    );
  }

  const cfg = RISK_CONFIG[riskLevel] || RISK_CONFIG.LOW;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-lg font-semibold text-white">분석 결과</h2>

      {/* Risk Badge */}
      <div className={`rounded-xl border p-4 ${cfg.bg} ${cfg.border} flex items-center gap-3`}>
        <span className={`w-3 h-3 rounded-full ${cfg.dot} animate-pulse`} />
        <div>
          <div className="text-xs text-gray-400 mb-0.5">위험 등급</div>
          <div className={`text-2xl font-bold ${cfg.text}`}>{cfg.label}</div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-3 gap-3">
        <StatCard
          label="최대 확률"
          value={(stats.max_prob * 100).toFixed(1)}
          unit="%"
        />
        <StatCard
          label="평균 확률"
          value={(stats.mean_prob * 100).toFixed(1)}
          unit="%"
        />
        <StatCard
          label="고위험 면적"
          value={stats.high_risk_pct.toFixed(1)}
          unit="%"
        />
      </div>
    </div>
  );
}

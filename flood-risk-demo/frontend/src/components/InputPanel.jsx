import React, { useRef } from "react";

function FileInput({ label, accept, file, onChange }) {
  const ref = useRef();
  return (
    <div className="flex flex-col gap-1">
      <label className="text-sm font-medium text-gray-300">{label}</label>
      <div
        className="border-2 border-dashed border-gray-600 rounded-lg p-4 cursor-pointer hover:border-blue-400 transition-colors flex flex-col items-center gap-2"
        onClick={() => ref.current.click()}
      >
        <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        {file ? (
          <span className="text-blue-400 text-sm font-medium">{file.name}</span>
        ) : (
          <span className="text-gray-500 text-sm">클릭하여 GeoTIFF 선택</span>
        )}
        <input
          ref={ref}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => onChange(e.target.files[0])}
        />
      </div>
    </div>
  );
}

export default function InputPanel({ onSubmit, loading }) {
  const [sarFile, setSarFile] = React.useState(null);
  const [demFile, setDemFile] = React.useState(null);
  const [precipitation, setPrecipitation] = React.useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!sarFile || !demFile || !precipitation.trim()) return;
    onSubmit({ sarFile, demFile, precipitation });
  };

  const isReady = sarFile && demFile && precipitation.trim() && !loading;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
      <h2 className="text-lg font-semibold text-white">입력 데이터</h2>

      <FileInput
        label="SAR 이미지 (GeoTIFF)"
        accept=".tif,.tiff"
        file={sarFile}
        onChange={setSarFile}
      />

      <FileInput
        label="DEM 이미지 (GeoTIFF)"
        accept=".tif,.tiff"
        file={demFile}
        onChange={setDemFile}
      />

      <div className="flex flex-col gap-1">
        <label className="text-sm font-medium text-gray-300">강수 정보</label>
        <textarea
          className="bg-gray-800 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white resize-none h-24 focus:outline-none focus:border-blue-400"
          placeholder="예: 최근 72시간 누적 강수량 250mm, 강도 시간당 45mm/h"
          value={precipitation}
          onChange={(e) => setPrecipitation(e.target.value)}
        />
      </div>

      <button
        type="submit"
        disabled={!isReady}
        className={`w-full py-3 rounded-lg font-semibold text-sm transition-all ${
          isReady
            ? "bg-blue-600 hover:bg-blue-500 text-white cursor-pointer"
            : "bg-gray-700 text-gray-500 cursor-not-allowed"
        }`}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            분석 중...
          </span>
        ) : "홍수 위험 예측"}
      </button>
    </form>
  );
}

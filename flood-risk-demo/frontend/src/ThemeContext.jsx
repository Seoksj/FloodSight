import React, { createContext, useContext, useState, useEffect } from "react";

const COLORS = {
  dark: {
    bgBase:       "#060c18",
    bgSurface:    "#0d1526",
    bgCard:       "#111d35",
    bgCardHover:  "#152040",
    bgInput:      "rgba(255,255,255,0.04)",
    bgOverlay:    "rgba(6,12,24,0.95)",
    bgNum:        "rgba(0,0,0,0.20)",
    border:       "rgba(255,255,255,0.06)",
    borderMid:    "rgba(255,255,255,0.10)",
    textPrimary:  "#e2e8f0",
    textSecond:   "#94a3b8",
    textMuted:    "#64748b",
    textFaint:    "#334155",
    pillActive:   "rgba(37,99,235,0.20)",
    pillActiveBorder: "rgba(37,99,235,0.40)",
    pillText:     "#60a5fa",
    mapBg:        "rgba(6,12,24,0.75)",
    toggleTrack:  "rgba(255,255,255,0.04)",
  },
  light: {
    bgBase:       "#eef2f7",
    bgSurface:    "#ffffff",
    bgCard:       "#f8fafc",
    bgCardHover:  "#f1f5f9",
    bgInput:      "rgba(0,0,0,0.04)",
    bgOverlay:    "rgba(255,255,255,0.97)",
    bgNum:        "rgba(0,0,0,0.05)",
    border:       "rgba(0,0,0,0.08)",
    borderMid:    "rgba(0,0,0,0.13)",
    textPrimary:  "#0f172a",
    textSecond:   "#334155",
    textMuted:    "#64748b",
    textFaint:    "#94a3b8",
    pillActive:   "rgba(37,99,235,0.12)",
    pillActiveBorder: "rgba(37,99,235,0.35)",
    pillText:     "#2563eb",
    mapBg:        "rgba(248,250,252,0.88)",
    toggleTrack:  "rgba(0,0,0,0.06)",
  },
};

const ThemeContext = createContext({ theme: "dark", c: COLORS.dark, toggle: () => {} });

export function ThemeProvider({ children }) {
  const saved  = () => localStorage.getItem("theme") || "dark";
  const [theme, setTheme] = useState(saved);
  const c = COLORS[theme];

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);

    // CSS 변수는 [data-theme] 규칙이 자동 처리 — JS override 불필요
  }, [theme]);

  const toggle = () => setTheme(t => t === "dark" ? "light" : "dark");

  return (
    <ThemeContext.Provider value={{ theme, c, toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);

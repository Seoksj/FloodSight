import React, { createContext, useContext, useState, useEffect } from "react";

export const COLORS = {
  light: {
    bg:          "#f4f2ef",
    surface:     "#ffffff",
    surface2:    "#faf9f7",
    elev:        "0 1px 2px rgba(28,25,20,.05),0 4px 16px rgba(28,25,20,.05)",
    border:      "#e7e3dd",
    border2:     "#efece7",
    text:        "#23211d",
    text2:       "#6c6860",
    text3:       "#a6a199",
    primary:     "#33507e",
    primarySoft: "#eaeff8",
    danger:      "#dd382e",
    alert:       "#e87d2c",
    caution:     "#d99e0b",
    safe:        "#1f9d57",
    dangerSoft:  "#fbe9e7",
    alertSoft:   "#fceede",
    cautionSoft: "#f8f0d6",
    safeSoft:    "#e6f4ec",
  },
  dark: {
    bg:          "#141519",
    surface:     "#1c1e24",
    surface2:    "#23262d",
    elev:        "0 1px 2px rgba(0,0,0,.3),0 6px 20px rgba(0,0,0,.35)",
    border:      "#2c2f37",
    border2:     "#262932",
    text:        "#ecead9",
    text2:       "#a3a7b0",
    text3:       "#71757e",
    primary:     "#7aa1e6",
    primarySoft: "#232b3a",
    danger:      "#f15a50",
    alert:       "#f0913f",
    caution:     "#e6b22a",
    safe:        "#34b46e",
    dangerSoft:  "#34201e",
    alertSoft:   "#352818",
    cautionSoft: "#322a14",
    safeSoft:    "#16291f",
  },
};

// 백엔드 grade 문자열 → 색상 키 매핑
export const GRADE_MAP = {
  안전: { key: "safe",    label: "안전" },
  주의: { key: "caution", label: "주의" },
  경보: { key: "alert",   label: "경보" },
  위험: { key: "danger",  label: "위험" },
};

export function gradeStyle(c, grade) {
  const g = GRADE_MAP[grade] ?? GRADE_MAP["안전"];
  return { color: c[g.key], bg: c[g.key + "Soft"], key: g.key, label: g.label };
}

const ThemeContext = createContext({ theme: "dark", c: COLORS.dark, toggle: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "dark");
  const c = COLORS[theme];

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    document.body.style.background = c.bg;
    document.body.style.color = c.text;
    localStorage.setItem("theme", theme);
  }, [theme, c]);

  return (
    <ThemeContext.Provider value={{ theme, c, toggle: () => setTheme(t => t === "dark" ? "light" : "dark") }}>
      {children}
    </ThemeContext.Provider>
  );
}

export const useTheme = () => useContext(ThemeContext);

"""
도시 침수 위험도 산출 엔진 (Urban Flood Risk Engine).

위험 등급:
  안전 score < 0.45 : #4CAF50
  주의 score < 0.60 : #FFC107
  경보 score < 0.75 : #FF9800
  위험 score >= 0.75 : #F44336
"""

from typing import Dict, Any

GRADE_CONFIG = {
    "안전": {"color": "#4CAF50", "opacity": 0.30, "en": "safe"},
    "주의": {"color": "#FFC107", "opacity": 0.45, "en": "caution"},
    "경보": {"color": "#FF9800", "opacity": 0.60, "en": "warning"},
    "위험": {"color": "#F44336", "opacity": 0.75, "en": "danger"},
}


def compute_urban_flood_risk(
    rainfall_1h: float,
    drainage_capacity: float,
    impervious_ratio: float,
    topo_depression: float,
    flood_history: float,
) -> float:
    """
    도시 침수 위험도 점수 [0, 1] 계산.

    강수강도_초과율 = min(rainfall_1h / drainage_capacity, 1.0)   × 0.40
    지형취약도                                                      × 0.30
    불투수율                                                        × 0.20
    침수이력                                                        × 0.10
    """
    rain_overload = min(rainfall_1h / max(drainage_capacity, 1.0), 1.0)

    return round(
        rain_overload    * 0.40
        + topo_depression  * 0.30
        + impervious_ratio * 0.20
        + flood_history    * 0.10,
        4,
    )


def water_level_bonus(wl: float, alert_level: float) -> float:
    """
    수위/경보수위 비율 → 위험도 보정값 [0, 0.10].
    비율 50% 미만: 0  / 50~100%: 선형 증가 → 최대 0.10
    """
    if alert_level <= 0:
        return 0.0
    ratio = wl / alert_level
    if ratio < 0.5:
        return 0.0
    return round(min((ratio - 0.5) * 0.20, 0.10), 4)


def score_to_grade(score: float, rainfall_1h: float = None) -> Dict[str, Any]:
    if score < 0.45:
        grade = "안전"
    elif score < 0.60:
        grade = "주의"
    elif score < 0.75:
        grade = "경보"
    else:
        grade = "위험"
    # 강수 없으면 최대 주의 — 취약성은 높아도 현재 위험 아님
    if rainfall_1h is not None and rainfall_1h < 5.0 and grade in ("경보", "위험"):
        grade = "주의"
    return {"grade": grade, "score": score, **GRADE_CONFIG[grade]}


def generate_urban_reason(meta: Dict, rainfall_1h: float, grade: str) -> str:
    """
    도시 침수 위험 근거 문장 생성.
    예: "신림동 — 현재 강수 45mm/hr, 하수도 용량(30mm) 초과 150%.
         불투수율 76%, 침수 이력 높음. 즉각적인 대피가 필요합니다."
    """
    name     = f"{meta.get('name', '')} ({meta.get('gu', '')})"
    cap      = meta.get("drainage_capacity", 30.0)
    imperv   = meta.get("impervious_ratio", 0.5)
    history  = meta.get("flood_history", 0.5)
    overload = rainfall_1h / max(cap, 1.0) * 100

    parts = [f"{name} — 현재 강수 {rainfall_1h:.0f}mm/hr."]

    if rainfall_1h > cap:
        parts.append(f"하수도 용량({cap:.0f}mm/hr) 초과 {overload:.0f}%.")
    else:
        parts.append(f"하수도 용량({cap:.0f}mm/hr)의 {overload:.0f}% 수준.")

    imperv_label = "매우 높음" if imperv > 0.75 else "높음" if imperv > 0.6 else "보통"
    parts.append(f"불투수율 {imperv*100:.0f}%({imperv_label}).")

    if history >= 0.35:
        parts.append("과거 침수 이력 매우 많음.")
    elif history >= 0.15:
        parts.append("과거 침수 이력 있음.")

    grade_msgs = {
        "안전": "현재 침수 위험 낮습니다.",
        "주의": "강수량 증가 시 침수 주의가 필요합니다.",
        "경보": "침수 위험 높음. 저지대·반지하 대피 준비를 권고합니다.",
        "위험": "즉각적인 대피가 필요합니다.",
    }
    parts.append(grade_msgs.get(grade, ""))

    return " ".join(parts)

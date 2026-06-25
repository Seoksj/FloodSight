"""
전국 주요 침수 취약 지역 데이터 + 도시 침수 위험도 GeoJSON 생성.

데이터 출처 (실제 연동 시):
  - 행정안전부 침수흔적도 (data.go.kr)
  - 국토부 VWORLD 읍면동 경계
  - 환경부 불투수면적률 DB

현재: 36개 주요 취약 지구 하드코딩 더미.
"""

import json
import math
import os
import random
import time
from typing import List, Dict, Any, Tuple

from risk_engine import compute_urban_flood_risk, score_to_grade, generate_urban_reason

# 실제 행정동 경계 (fetch_boundaries.py 로 생성)
_BOUNDARIES_PATH = os.path.join(os.path.dirname(__file__), "district_boundaries.json")
_BOUNDARIES: Dict[str, list] = {}

def _load_boundaries():
    global _BOUNDARIES
    if os.path.exists(_BOUNDARIES_PATH):
        try:
            with open(_BOUNDARIES_PATH, encoding="utf-8") as f:
                _BOUNDARIES = json.load(f)
        except Exception:
            _BOUNDARIES = {}

_load_boundaries()

# ──────────────────────────────────────────────────────────────
# 정적 취약지 메타데이터
#   drainage_capacity : 하수도 설계 용량 (mm/hr)
#   impervious_ratio  : 불투수율 0~1
#   topo_depression   : 지형 취약도 0~1 (1=극저지대/분지)
#   flood_history     : 침수 이력 지수 0~1
# ──────────────────────────────────────────────────────────────
DISTRICTS: List[Dict[str, Any]] = [
    # ── 서울 ──────────────────────────────────────────────────
    {"id":"SL01","name":"역삼1동","gu":"강남구","city":"서울",
     "lat":37.499,"lon":127.041,"drainage_capacity":80.0,"impervious_ratio":0.82,
     "topo_depression":0.72,"flood_history":0.90},
    {"id":"SL02","name":"신림동","gu":"관악구","city":"서울",
     "lat":37.484,"lon":126.929,"drainage_capacity":30.0,"impervious_ratio":0.76,
     "topo_depression":0.80,"flood_history":0.95},   # 2022 반지하 침수
    {"id":"SL03","name":"상도3동","gu":"동작구","city":"서울",
     "lat":37.503,"lon":126.954,"drainage_capacity":35.0,"impervious_ratio":0.74,
     "topo_depression":0.65,"flood_history":0.70},
    {"id":"SL04","name":"화곡8동","gu":"강서구","city":"서울",
     "lat":37.548,"lon":126.849,"drainage_capacity":30.0,"impervious_ratio":0.79,
     "topo_depression":0.68,"flood_history":0.75},
    {"id":"SL05","name":"천호동","gu":"강동구","city":"서울",
     "lat":37.538,"lon":127.128,"drainage_capacity":50.0,"impervious_ratio":0.75,
     "topo_depression":0.60,"flood_history":0.65},
    {"id":"SL06","name":"여의동","gu":"영등포구","city":"서울",
     "lat":37.521,"lon":126.924,"drainage_capacity":55.0,"impervious_ratio":0.71,
     "topo_depression":0.82,"flood_history":0.80},   # 한강 접경 저지대
    {"id":"SL07","name":"신도림동","gu":"구로구","city":"서울",
     "lat":37.509,"lon":126.890,"drainage_capacity":30.0,"impervious_ratio":0.80,
     "topo_depression":0.75,"flood_history":0.85},   # 도림천
    {"id":"SL08","name":"독산3동","gu":"금천구","city":"서울",
     "lat":37.460,"lon":126.895,"drainage_capacity":30.0,"impervious_ratio":0.77,
     "topo_depression":0.58,"flood_history":0.68},
    {"id":"SL09","name":"공릉2동","gu":"노원구","city":"서울",
     "lat":37.625,"lon":127.076,"drainage_capacity":35.0,"impervious_ratio":0.66,
     "topo_depression":0.50,"flood_history":0.55},
    {"id":"SL10","name":"성수2가","gu":"성동구","city":"서울",
     "lat":37.544,"lon":127.057,"drainage_capacity":50.0,"impervious_ratio":0.73,
     "topo_depression":0.70,"flood_history":0.72},
    {"id":"SL11","name":"불광2동","gu":"은평구","city":"서울",
     "lat":37.617,"lon":126.927,"drainage_capacity":30.0,"impervious_ratio":0.68,
     "topo_depression":0.62,"flood_history":0.60},   # 불광천
    {"id":"SL12","name":"홍은2동","gu":"서대문구","city":"서울",
     "lat":37.587,"lon":126.944,"drainage_capacity":35.0,"impervious_ratio":0.65,
     "topo_depression":0.55,"flood_history":0.58},
    {"id":"SL13","name":"방배3동","gu":"서초구","city":"서울",
     "lat":37.479,"lon":126.990,"drainage_capacity":65.0,"impervious_ratio":0.70,
     "topo_depression":0.45,"flood_history":0.50},
    {"id":"SL14","name":"잠실6동","gu":"송파구","city":"서울",
     "lat":37.511,"lon":127.102,"drainage_capacity":60.0,"impervious_ratio":0.74,
     "topo_depression":0.58,"flood_history":0.62},   # 탄천 접경
    {"id":"SL15","name":"합정동","gu":"마포구","city":"서울",
     "lat":37.549,"lon":126.909,"drainage_capacity":40.0,"impervious_ratio":0.72,
     "topo_depression":0.65,"flood_history":0.68},
    {"id":"SL16","name":"봉천동","gu":"관악구","city":"서울",
     "lat":37.478,"lon":126.950,"drainage_capacity":30.0,"impervious_ratio":0.75,
     "topo_depression":0.78,"flood_history":0.88},
    {"id":"SL17","name":"목동","gu":"양천구","city":"서울",
     "lat":37.527,"lon":126.874,"drainage_capacity":50.0,"impervious_ratio":0.72,
     "topo_depression":0.70,"flood_history":0.73},
    {"id":"SL18","name":"개봉동","gu":"구로구","city":"서울",
     "lat":37.496,"lon":126.864,"drainage_capacity":30.0,"impervious_ratio":0.76,
     "topo_depression":0.63,"flood_history":0.67},
    {"id":"SL19","name":"신촌동","gu":"서대문구","city":"서울",
     "lat":37.556,"lon":126.937,"drainage_capacity":35.0,"impervious_ratio":0.70,
     "topo_depression":0.50,"flood_history":0.55},
    {"id":"SL20","name":"도봉동","gu":"도봉구","city":"서울",
     "lat":37.669,"lon":127.048,"drainage_capacity":35.0,"impervious_ratio":0.62,
     "topo_depression":0.48,"flood_history":0.50},
    # ── 인천 ──────────────────────────────────────────────────
    {"id":"IC01","name":"부평2동","gu":"부평구","city":"인천",
     "lat":37.506,"lon":126.724,"drainage_capacity":30.0,"impervious_ratio":0.79,
     "topo_depression":0.72,"flood_history":0.80},   # 굴포천
    {"id":"IC02","name":"계산3동","gu":"계양구","city":"인천",
     "lat":37.537,"lon":126.738,"drainage_capacity":35.0,"impervious_ratio":0.68,
     "topo_depression":0.60,"flood_history":0.65},
    {"id":"IC03","name":"주안5동","gu":"미추홀구","city":"인천",
     "lat":37.462,"lon":126.661,"drainage_capacity":30.0,"impervious_ratio":0.77,
     "topo_depression":0.65,"flood_history":0.70},
    # ── 부산 ──────────────────────────────────────────────────
    {"id":"BS01","name":"온천4동","gu":"동래구","city":"부산",
     "lat":35.199,"lon":129.085,"drainage_capacity":35.0,"impervious_ratio":0.71,
     "topo_depression":0.68,"flood_history":0.75},   # 온천천
    {"id":"BS02","name":"범천동","gu":"부산진구","city":"부산",
     "lat":35.151,"lon":129.059,"drainage_capacity":30.0,"impervious_ratio":0.78,
     "topo_depression":0.73,"flood_history":0.82},   # 동천
    {"id":"BS03","name":"서동","gu":"금정구","city":"부산",
     "lat":35.234,"lon":129.090,"drainage_capacity":25.0,"impervious_ratio":0.60,
     "topo_depression":0.55,"flood_history":0.60},
    {"id":"BS04","name":"하단동","gu":"사하구","city":"부산",
     "lat":35.097,"lon":128.974,"drainage_capacity":35.0,"impervious_ratio":0.69,
     "topo_depression":0.70,"flood_history":0.73},
    # ── 대구 ──────────────────────────────────────────────────
    {"id":"DG01","name":"두류3동","gu":"달서구","city":"대구",
     "lat":35.852,"lon":128.565,"drainage_capacity":30.0,"impervious_ratio":0.72,
     "topo_depression":0.65,"flood_history":0.70},   # 신천
    {"id":"DG02","name":"침산1동","gu":"북구","city":"대구",
     "lat":35.896,"lon":128.572,"drainage_capacity":30.0,"impervious_ratio":0.68,
     "topo_depression":0.62,"flood_history":0.65},
    # ── 광주 ──────────────────────────────────────────────────
    {"id":"GJ01","name":"용봉동","gu":"북구","city":"광주",
     "lat":35.178,"lon":126.912,"drainage_capacity":30.0,"impervious_ratio":0.65,
     "topo_depression":0.55,"flood_history":0.60},
    {"id":"GJ02","name":"농성동","gu":"서구","city":"광주",
     "lat":35.149,"lon":126.888,"drainage_capacity":25.0,"impervious_ratio":0.70,
     "topo_depression":0.67,"flood_history":0.72},
    # ── 대전 ──────────────────────────────────────────────────
    {"id":"DJ01","name":"봉명동","gu":"유성구","city":"대전",
     "lat":36.355,"lon":127.345,"drainage_capacity":30.0,"impervious_ratio":0.62,
     "topo_depression":0.55,"flood_history":0.58},
    {"id":"DJ02","name":"대흥동","gu":"중구","city":"대전",
     "lat":36.326,"lon":127.426,"drainage_capacity":30.0,"impervious_ratio":0.68,
     "topo_depression":0.60,"flood_history":0.65},
    # ── 경기 ──────────────────────────────────────────────────
    {"id":"GG01","name":"인계동","gu":"팔달구","city":"수원",
     "lat":37.262,"lon":127.028,"drainage_capacity":35.0,"impervious_ratio":0.74,
     "topo_depression":0.60,"flood_history":0.65},
    {"id":"GG02","name":"금광동","gu":"중원구","city":"성남",
     "lat":37.447,"lon":127.147,"drainage_capacity":35.0,"impervious_ratio":0.71,
     "topo_depression":0.58,"flood_history":0.62},
    {"id":"GG03","name":"중동","gu":"원미구","city":"부천",
     "lat":37.503,"lon":126.769,"drainage_capacity":30.0,"impervious_ratio":0.78,
     "topo_depression":0.68,"flood_history":0.72},
]


def _make_polygon(lat: float, lon: float, radius_deg: float = 0.02, n: int = 16) -> list:
    """원형 근사 폴리곤 (실제 경계 없을 때 폴백)."""
    rng = random.Random(hash(f"{lat:.3f}{lon:.3f}"))
    coords = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        r = radius_deg * (0.85 + rng.uniform(-0.12, 0.12))
        coords.append([
            round(lon + r * math.cos(angle) * 1.2, 6),
            round(lat + r * math.sin(angle) * 0.9, 6),
        ])
    coords.append(coords[0])
    return [coords]


def _get_polygon(district_id: str, lat: float, lon: float) -> list:
    """실제 행정동 경계 반환. 없으면 원형 근사."""
    if district_id in _BOUNDARIES:
        return _BOUNDARIES[district_id]
    return _make_polygon(lat, lon)


def _current_regional_rainfall() -> Dict[str, float]:
    """
    현재 10분 구간 기준 지역별 강수량 생성 (더미).
    실제로는 KMA API 호출.
    """
    t_bucket = int(time.time() / 600)
    result = {}
    for city in {d["city"] for d in DISTRICTS}:
        rng = random.Random(hash((t_bucket, city)))
        result[city] = round(rng.uniform(0.0, 90.0), 1)
    return result


def _forecast_rainfall(meta: Dict, current_1h: float) -> Dict:
    """현재 강수량 기반 1h/3h 예보 더미 생성."""
    rng = random.Random(hash((int(time.time() / 600), meta["id"], "fc")))
    trend = rng.choice([0.7, 0.85, 1.0, 1.1, 1.25, 1.4])
    r_1h = round(current_1h * trend, 1)
    r_3h = round(r_1h * rng.uniform(0.85, 1.15), 1)
    return {"1h": {"rainfall": r_1h}, "3h": {"rainfall": r_3h}}


def build_urban_risk_data() -> Tuple[List[Dict], Dict]:
    """
    전체 지구 위험도 계산 → (enriched_list, current GeoJSON) 반환.
    scheduler에서 호출. 예보 데이터도 포함.
    ML 블렌딩은 scheduler가 predictor 호출 후 apply_ml_scores()로 수행.
    """
    regional_rain = _current_regional_rainfall()
    enriched = []

    for meta in DISTRICTS:
        city_rain = regional_rain.get(meta["city"], 10.0)
        rng = random.Random(hash((int(time.time() / 600), meta["id"])))
        rainfall_1h = round(city_rain * rng.uniform(0.8, 1.2), 1)

        rule_score = compute_urban_flood_risk(
            rainfall_1h        = rainfall_1h,
            drainage_capacity  = meta["drainage_capacity"],
            impervious_ratio   = meta["impervious_ratio"],
            topo_depression    = meta["topo_depression"],
            flood_history      = meta["flood_history"],
        )
        grade_info = score_to_grade(rule_score)
        reason     = generate_urban_reason(meta, rainfall_1h, grade_info["grade"])
        forecast   = _forecast_rainfall(meta, rainfall_1h)

        # 예보 시나리오별 rule-based 스코어 계산
        for h_key in ("1h", "3h"):
            r_fc = forecast[h_key]["rainfall"]
            fc_score = compute_urban_flood_risk(
                rainfall_1h        = r_fc,
                drainage_capacity  = meta["drainage_capacity"],
                impervious_ratio   = meta["impervious_ratio"],
                topo_depression    = meta["topo_depression"],
                flood_history      = meta["flood_history"],
            )
            fc_grade = score_to_grade(fc_score)
            forecast[h_key].update({
                "rule_score": fc_score,
                "risk_score": fc_score,   # ML 블렌딩 전 초기값
                "grade":      fc_grade["grade"],
                "color":      fc_grade["color"],
            })

        enriched.append({
            **meta,
            "rainfall_1h":       rainfall_1h,
            "rain_overload_pct": round(rainfall_1h / max(meta["drainage_capacity"], 1) * 100, 1),
            "rule_score":        rule_score,
            "risk_score":        rule_score,   # ML 블렌딩 전 초기값
            "grade":             grade_info["grade"],
            "color":             grade_info["color"],
            "reason":            reason,
            "forecast":          forecast,
        })

    geojson = _build_geojson(enriched, horizon="current")
    return enriched, geojson


def apply_ml_scores(enriched: List[Dict], ml_scores: Dict[str, Dict]) -> List[Dict]:
    """
    predictor.predict_all_horizons() 결과를 enriched 리스트에 적용.
    rule_score와 ml_score를 블렌딩하여 risk_score 갱신.
    """
    from predictor import blend

    for d in enriched:
        did = d["id"]
        if did not in ml_scores:
            continue
        ml = ml_scores[did]

        d["risk_score"] = blend(d["rule_score"], ml["current"])
        gi = score_to_grade(d["risk_score"])
        d["grade"] = gi["grade"]
        d["color"] = gi["color"]
        d["reason"] = generate_urban_reason(d, d["rainfall_1h"], d["grade"])

        for h_key in ("1h", "3h"):
            fc = d["forecast"][h_key]
            fc["risk_score"] = blend(fc["rule_score"], ml[h_key])
            fc_gi = score_to_grade(fc["risk_score"])
            fc["grade"] = fc_gi["grade"]
            fc["color"] = fc_gi["color"]

    return enriched


def build_geojson_for_horizon(enriched: List[Dict], horizon: str) -> Dict:
    """horizon별 GeoJSON 생성 (current / 1h / 3h)."""
    return _build_geojson(enriched, horizon=horizon)


def _build_geojson(districts: List[Dict], horizon: str = "current") -> Dict:
    features = []
    for d in districts:
        if horizon in ("1h", "3h"):
            fc   = d.get("forecast", {}).get(horizon, {})
            risk = fc.get("risk_score", d["risk_score"])
            gi   = score_to_grade(risk)
            grade, color = gi["grade"], gi["color"]
            rain = fc.get("rainfall", d["rainfall_1h"])
        else:
            risk  = d["risk_score"]
            grade = d["grade"]
            color = d["color"]
            rain  = d["rainfall_1h"]

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": _get_polygon(d["id"], d["lat"], d["lon"]),
            },
            "properties": {
                "id":              d["id"],
                "name":            d["name"],
                "gu":              d["gu"],
                "city":            d["city"],
                "grade":           grade,
                "color":           color,
                "opacity":         _opacity(grade),
                "risk_score":      round(risk, 3),
                "rainfall_1h":     rain,
                "rain_overload_pct": round(rain / max(d["drainage_capacity"], 1) * 100, 1),
                "drainage_capacity": d["drainage_capacity"],
                "reason":          d.get("reason", ""),
                "horizon":         horizon,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def find_nearest(lat: float, lon: float) -> Dict:
    """위경도 → 가장 가까운 지구 반환 (캐시된 enriched 데이터에서)."""
    best, best_dist = None, float("inf")
    for d in DISTRICTS:
        dist = math.hypot(d["lat"] - lat, d["lon"] - lon)
        if dist < best_dist:
            best_dist, best = dist, d
    return best, best_dist * 111  # km


def _opacity(grade: str) -> float:
    return {"안전": 0.30, "주의": 0.45, "경보": 0.60, "위험": 0.75}.get(grade, 0.4)

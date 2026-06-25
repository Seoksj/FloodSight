"""
관측소 포인트 데이터 → IDW 격자 보간 → GeoJSON FeatureCollection.

격자 범위: 위도 34~38, 경도 126~130, 간격 0.05도
총 격자: 80 × 80 = 6,400 폴리곤
"""

import math
from typing import List, Dict, Any, Tuple

import numpy as np

from risk_engine import score_to_grade

# 격자 설정
LAT_MIN, LAT_MAX = 34.0, 38.0
LON_MIN, LON_MAX = 126.0, 130.0
RESOLUTION = 0.05


def _idw(
    points: np.ndarray,   # (N, 2) [lat, lon]
    values: np.ndarray,   # (N,)
    query: np.ndarray,    # (M, 2) [lat, lon]
    power: float = 2.0,
) -> np.ndarray:
    """Inverse Distance Weighting 보간."""
    # (M, N) 거리 행렬 (단위: 도 — 짧은 거리에서 충분)
    diff = query[:, None, :] - points[None, :, :]        # (M, N, 2)
    dist = np.sqrt((diff ** 2).sum(axis=2)) + 1e-10      # (M, N)

    w = 1.0 / (dist ** power)                            # (M, N)
    return (w * values[None, :]).sum(axis=1) / w.sum(axis=1)


def _make_polygon_coords(lat: float, lon: float, res: float = RESOLUTION) -> list:
    """격자 셀 → GeoJSON Polygon 좌표 (시계 반대 방향)."""
    half = res / 2
    return [[
        [lon - half, lat - half],
        [lon + half, lat - half],
        [lon + half, lat + half],
        [lon - half, lat + half],
        [lon - half, lat - half],
    ]]


def build_risk_geojson(enriched_stations: List[Dict[str, Any]]) -> Dict:
    """
    관측소 데이터 → IDW 보간 → GeoJSON FeatureCollection 반환.

    Args:
        enriched_stations: risk_engine.enrich_station() 적용된 관측소 리스트
    Returns:
        GeoJSON FeatureCollection (격자 폴리곤)
    """
    if not enriched_stations:
        return {"type": "FeatureCollection", "features": []}

    # 격자 중심 좌표 생성
    lats = np.arange(LAT_MIN + RESOLUTION / 2, LAT_MAX, RESOLUTION)
    lons = np.arange(LON_MIN + RESOLUTION / 2, LON_MAX, RESOLUTION)
    grid_lat, grid_lon = np.meshgrid(lats, lons, indexing="ij")  # (rows, cols)

    query_pts = np.column_stack([grid_lat.ravel(), grid_lon.ravel()])  # (M, 2)

    station_pts = np.array([[s["lat"], s["lon"]] for s in enriched_stations])
    station_scores = np.array([s["risk_score"] for s in enriched_stations])

    # IDW 보간
    interp_scores = _idw(station_pts, station_scores, query_pts)
    interp_scores = np.clip(interp_scores, 0.0, 1.0)

    features = []
    for i, (lat, lon, score) in enumerate(
        zip(query_pts[:, 0], query_pts[:, 1], interp_scores)
    ):
        grade_info = score_to_grade(float(score))
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": _make_polygon_coords(lat, lon),
            },
            "properties": {
                "score":   round(float(score), 3),
                "grade":   grade_info["grade"],
                "color":   grade_info["color"],
                "opacity": grade_info["opacity"],
            },
        })

    return {"type": "FeatureCollection", "features": features}


def interpolate_point(
    enriched_stations: List[Dict[str, Any]],
    lat: float,
    lon: float,
) -> Dict[str, Any]:
    """
    특정 위경도 지점의 위험도 보간 반환.
    가장 가까운 관측소 정보도 함께 반환.
    """
    if not enriched_stations:
        return {"risk_score": 0.0, "grade": "안전", "nearest_station": None}

    station_pts = np.array([[s["lat"], s["lon"]] for s in enriched_stations])
    station_scores = np.array([s["risk_score"] for s in enriched_stations])

    query = np.array([[lat, lon]])
    score = float(_idw(station_pts, station_scores, query)[0])
    score = min(max(score, 0.0), 1.0)

    # 가장 가까운 관측소 찾기
    dists = np.sqrt(((station_pts - np.array([lat, lon])) ** 2).sum(axis=1))
    nearest = enriched_stations[int(np.argmin(dists))]

    grade_info = score_to_grade(score)
    return {
        "lat":             lat,
        "lon":             lon,
        "risk_score":      round(score, 4),
        "grade":           grade_info["grade"],
        "color":           grade_info["color"],
        "reason":          nearest.get("reason", ""),
        "nearest_station": {
            "name":         nearest["name"],
            "distance_km":  round(float(np.min(dists)) * 111, 1),
            "water_level":  nearest.get("water_level"),
            "alert_level":  nearest.get("alert_level"),
            "rainfall_1h":  nearest.get("rainfall_1h"),
        },
    }

"""
FastAPI 메인 앱 — 도시 침수 위험도 모니터링.

GET /health          — 서버 상태
GET /risk            — 전체 지구 위험도 GeoJSON
GET /risk/point      — 특정 위경도 위험도 + 근거
GET /districts       — 지구별 현황 리스트 (경보 이상 우선)
POST /predict        — ML 추론 엔드포인트 (기존 유지)
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from cache import cache
from scheduler import start_scheduler, stop_scheduler
from spatial.districts import find_nearest, build_urban_risk_data
from risk_engine import compute_urban_flood_risk, score_to_grade, generate_urban_reason

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="도시 침수 위험도 API", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://seoksj.github.io",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    lu = cache.last_updated
    return {
        "status":        "ok",
        "cache_ready":   cache.is_ready,
        "last_updated":  lu.isoformat() + "Z" if lu else None,
        "district_count": len(cache.stations),
    }


@app.get("/risk")
async def get_risk(
    horizon: str = Query("current", description="예보 시간대 (current / 1h / 3h)"),
):
    """지구별 침수 위험도 GeoJSON FeatureCollection."""
    if horizon not in ("current", "1h", "3h"):
        raise HTTPException(400, "horizon은 current / 1h / 3h 중 하나여야 합니다.")
    geojson = cache.get_geojson(horizon)
    if not geojson:
        raise HTTPException(503, "데이터 수집 중입니다. 잠시 후 재시도.")
    return geojson


@app.get("/risk/point")
async def get_risk_point(
    lat: float = Query(..., ge=33.0, le=39.0),
    lon: float = Query(..., ge=124.0, le=132.0),
):
    """특정 위경도 → 가장 가까운 취약 지구의 위험도 + 근거."""
    districts = cache.stations
    if not districts:
        raise HTTPException(503, "데이터 수집 중입니다.")

    # 캐시에서 nearest 탐색
    best, best_dist = None, float("inf")
    import math
    for d in districts:
        dist = math.hypot(d["lat"] - lat, d["lon"] - lon)
        if dist < best_dist:
            best_dist, best = dist, d

    if not best:
        raise HTTPException(404, "근처 위험 지구를 찾을 수 없습니다.")

    return {
        "lat":             lat,
        "lon":             lon,
        "nearest_district": {
            "id":    best["id"],
            "name":  best["name"],
            "gu":    best["gu"],
            "city":  best["city"],
            "distance_km": round(best_dist * 111, 1),
        },
        "risk_score":      best["risk_score"],
        "grade":           best["grade"],
        "color":           best["color"],
        "rainfall_1h":     best["rainfall_1h"],
        "rain_overload_pct": best["rain_overload_pct"],
        "drainage_capacity": best["drainage_capacity"],
        "reason":          best["reason"],
    }


@app.get("/districts")
async def get_districts(
    city:  Optional[str] = Query(None, description="도시 필터 (서울/부산/...)"),
    grade: Optional[str] = Query(None, description="등급 필터 (안전/주의/경보/위험)"),
):
    """침수 취약 지구 현황 — 경보 이상 우선 정렬."""
    districts = cache.stations
    if not districts:
        raise HTTPException(503, "데이터 수집 중입니다.")

    if city:
        districts = [d for d in districts if d.get("city") == city]
    if grade:
        districts = [d for d in districts if d.get("grade") == grade]

    order = {"위험": 0, "경보": 1, "주의": 2, "안전": 3}
    districts = sorted(districts, key=lambda d: order.get(d.get("grade", "안전"), 4))

    return {"districts": districts, "count": len(districts)}


@app.post("/predict")
async def predict_endpoint(
    sar:           UploadFile = File(...),
    dem:           UploadFile = File(...),
    precipitation: str        = Form(...),
):
    try:
        from inference import predict as ml_predict, initialize
        initialize()
        prob_map, risk_level, stats = ml_predict(
            await sar.read(), await dem.read(), precipitation
        )
        return {"prob_map": prob_map.tolist(), "risk_level": risk_level, "stats": stats}
    except Exception as e:
        logger.exception("ML 추론 실패")
        raise HTTPException(500, str(e))

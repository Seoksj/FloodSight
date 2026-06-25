"""
기상청 동네예보 API 클라이언트.
격자 좌표 기반 1~6시간 강수량 예보 반환.
API_KEY 없으면 더미 예보 반환.

공공데이터포털: KMA_API_KEY 환경변수
Endpoint: https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst
"""

import os
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

import httpx

logger = logging.getLogger(__name__)

KMA_API_KEY = os.getenv("KMA_API_KEY", "")
BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# 격자 좌표 변환 상수 (기상청 Lambert 투영 → 격자)
RE  = 6371.00877
GRID = 5.0
SLAT1 = 30.0
SLAT2 = 60.0
OLON  = 126.0
OLAT  = 38.0
XO    = 43
YO    = 136


def _latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    """위경도 → 기상청 격자 좌표 변환."""
    import math
    DEGRAD = math.pi / 180.0
    re   = RE / GRID
    slat1 = SLAT1 * DEGRAD
    slat2 = SLAT2 * DEGRAD
    olon  = OLON * DEGRAD
    olat  = OLAT * DEGRAD

    sn = math.tan(math.pi * 0.25 + slat2 * 0.5) / math.tan(math.pi * 0.25 + slat1 * 0.5)
    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(sn)
    sf = math.tan(math.pi * 0.25 + slat1 * 0.5)
    sf = (sf ** sn) * math.cos(slat1) / sn
    ro = math.tan(math.pi * 0.25 + olat * 0.5)
    ro = re * sf / (ro ** sn)

    ra = math.tan(math.pi * 0.25 + lat * DEGRAD * 0.5)
    ra = re * sf / (ra ** sn)
    theta = lon * DEGRAD - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    nx = int(ra * math.sin(theta) + XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + YO + 0.5)
    return nx, ny


def _dummy_forecast(lat: float, lon: float) -> Dict[str, Any]:
    """더미 강수 예보 생성."""
    rng = random.Random(int(lat * 100 + lon * 100))
    now = datetime.now()
    forecasts = {}
    for h in range(1, 7):
        t = now + timedelta(hours=h)
        forecasts[f"+{h}h"] = {
            "time": t.strftime("%Y%m%d %H:%M"),
            "rainfall_mm": round(rng.uniform(0, 20), 1),
            "sky": rng.choice(["맑음", "구름많음", "흐림"]),
        }
    return {
        "lat": lat,
        "lon": lon,
        "grid_nx": 60,
        "grid_ny": 127,
        "source": "dummy",
        "forecasts": forecasts,
    }


async def fetch_forecast(lat: float, lon: float) -> Dict[str, Any]:
    """
    위경도 기준 1~6시간 강수량 예보 조회.
    API_KEY 없으면 더미 반환.
    """
    if not KMA_API_KEY:
        return _dummy_forecast(lat, lon)

    nx, ny = _latlon_to_grid(lat, lon)
    now = datetime.now()
    # 기상청은 매 3시간 예보 (02, 05, 08, 11, 14, 17, 20, 23시 발표)
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    base_hour = max(h for h in base_hours if h <= now.hour) if now.hour >= 2 else 23
    base_date = now.strftime("%Y%m%d") if now.hour >= 2 else (now - timedelta(days=1)).strftime("%Y%m%d")

    params = {
        "serviceKey": KMA_API_KEY,
        "numOfRows": 50,
        "pageNo": 1,
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": f"{base_hour:02d}00",
        "nx": nx,
        "ny": ny,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(BASE_URL, params=params)
        data = resp.json()
        items = data["response"]["body"]["items"]["item"]
        forecasts = {}
        for item in items:
            if item["category"] == "PCP":
                fcst_time = item["fcstTime"]
                val = item["fcstValue"]
                forecasts[fcst_time] = {"rainfall_mm": val if val != "강수없음" else 0}
        return {
            "lat": lat, "lon": lon,
            "grid_nx": nx, "grid_ny": ny,
            "source": "kma",
            "forecasts": forecasts,
        }
    except Exception as e:
        logger.warning(f"기상청 API 실패: {e} → 더미 반환")
        return _dummy_forecast(lat, lon)

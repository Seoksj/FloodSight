"""
기상청 API 클라이언트.

초단기실황 (getUltraSrtNcst)  → 현재 강수량 (RN1: 1시간 강수량)
단기예보   (getVilageFcst)     → 1h / 3h 예보 강수량 (PCP)

KMA_API_KEY 없거나 호출 실패 시 더미 반환.
"""

import asyncio
import os
import math
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Tuple

import httpx

logger = logging.getLogger(__name__)

KMA_API_KEY = os.getenv("KMA_API_KEY", "")

_NCST_URL  = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
_FCST_URL  = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"

# ── Lambert 격자 변환 상수 ──────────────────────────────────────
_RE    = 6371.00877
_GRID  = 5.0
_SLAT1 = 30.0
_SLAT2 = 60.0
_OLON  = 126.0
_OLAT  = 38.0
_XO    = 43
_YO    = 136


def latlon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    """위경도 → KMA Lambert 격자 (nx, ny). 외부 모듈에서 사용 가능."""
    return _latlon_to_grid(lat, lon)


def _latlon_to_grid(lat: float, lon: float) -> Tuple[int, int]:
    DEGRAD = math.pi / 180.0
    re    = _RE / _GRID
    slat1 = _SLAT1 * DEGRAD
    slat2 = _SLAT2 * DEGRAD
    olon  = _OLON  * DEGRAD
    olat  = _OLAT  * DEGRAD

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / \
         math.log(math.tan(math.pi * .25 + slat2 * .5) / math.tan(math.pi * .25 + slat1 * .5))
    sf = (math.tan(math.pi * .25 + slat1 * .5) ** sn) * math.cos(slat1) / sn
    ro = re * sf / (math.tan(math.pi * .25 + olat * .5) ** sn)

    ra    = re * sf / (math.tan(math.pi * .25 + lat * DEGRAD * .5) ** sn)
    theta = (lon * DEGRAD - olon) * sn

    nx = int(ra * math.sin(theta) + _XO + 0.5)
    ny = int(ro - ra * math.cos(theta) + _YO + 0.5)
    return nx, ny


def _parse_pcp(val: str) -> float:
    """기상청 강수량 문자열 → float mm/hr."""
    if not val or val in ("강수없음", "-"):
        return 0.0
    val = val.replace("mm", "").replace("MM", "").strip()
    if "미만" in val:
        return 0.5
    try:
        return float(val)
    except ValueError:
        return 0.0


def _kst_now() -> datetime:
    """현재 KST 시각 반환."""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)


# ── 초단기실황: 현재 강수량 ───────────────────────────────────────

async def fetch_current_rainfall(lat: float, lon: float) -> float:
    """
    초단기실황 API → 현재 1시간 강수량(mm/hr) 반환.
    실패 시 -1.0 반환 (caller가 더미로 대체).
    """
    if not KMA_API_KEY:
        return -1.0

    nx, ny = _latlon_to_grid(lat, lon)
    now = _kst_now()
    # 초단기실황은 매 정시 + 30분 발표 (약 10분 지연)
    # → 현재 시각 기준으로 가장 가까운 정시로 내림
    base_dt = now.replace(minute=0, second=0, microsecond=0)
    if now.minute < 40:          # 발표 전이면 1시간 전 사용
        base_dt -= timedelta(hours=1)

    params = {
        "serviceKey": KMA_API_KEY,
        "numOfRows":  60,
        "pageNo":     1,
        "dataType":   "JSON",
        "base_date":  base_dt.strftime("%Y%m%d"),
        "base_time":  base_dt.strftime("%H%M"),
        "nx": nx,
        "ny": ny,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_NCST_URL, params=params)
        items = resp.json()["response"]["body"]["items"]["item"]
        for item in items:
            if item["category"] == "RN1":
                return _parse_pcp(item["obsrValue"])
        return 0.0
    except Exception as e:
        logger.warning(f"초단기실황 API 실패 ({lat},{lon}): {e}")
        return -1.0


# ── 단기예보: 1h / 3h 강수량 ─────────────────────────────────────

async def fetch_forecast_rainfall(lat: float, lon: float) -> Dict[str, float]:
    """
    단기예보 API → {"1h": mm, "3h": mm} 반환.
    실패 시 None 반환.
    """
    if not KMA_API_KEY:
        return None

    nx, ny = _latlon_to_grid(lat, lon)
    now = _kst_now()

    # 발표 시각: 02 05 08 11 14 17 20 23시 (매 3시간)
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    # 현재 시각 기준 가장 최근 발표 시각
    past = [h for h in base_hours if h <= now.hour]
    if past:
        base_hour = past[-1]
        base_date = now.strftime("%Y%m%d")
    else:
        base_hour = 23
        base_date = (now - timedelta(days=1)).strftime("%Y%m%d")

    params = {
        "serviceKey": KMA_API_KEY,
        "numOfRows":  300,
        "pageNo":     1,
        "dataType":   "JSON",
        "base_date":  base_date,
        "base_time":  f"{base_hour:02d}00",
        "nx": nx,
        "ny": ny,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_FCST_URL, params=params)
        items = resp.json()["response"]["body"]["items"]["item"]

        # 예보 시각별 PCP 추출
        pcp_by_time: Dict[str, float] = {}
        for item in items:
            if item["category"] == "PCP":
                pcp_by_time[item["fcstTime"]] = _parse_pcp(item["fcstValue"])

        if not pcp_by_time:
            return None

        times = sorted(pcp_by_time.keys())
        # 현재 시각 기준 +1h / +3h 예보 슬롯 찾기
        target_1h = (now + timedelta(hours=1)).strftime("%H00")
        target_3h = (now + timedelta(hours=3)).strftime("%H00")

        r_1h = pcp_by_time.get(target_1h) or (pcp_by_time[times[0]] if times else 0.0)
        r_3h = pcp_by_time.get(target_3h) or (pcp_by_time[times[min(2, len(times)-1)]] if times else 0.0)

        return {"1h": r_1h, "3h": r_3h}

    except Exception as e:
        logger.warning(f"단기예보 API 실패 ({lat},{lon}): {e}")
        return None


# ── 도시 대표 좌표 ────────────────────────────────────────────────
SEOUL_LAT   = 37.5715
SEOUL_LON   = 126.9769
INCHEON_LAT = 37.4563   # 인천시청
INCHEON_LON = 126.7052


async def fetch_city_rainfall(lat: float, lon: float) -> Dict[str, Any]:
    """특정 좌표 기준 현재 + 1h/3h 강수량 반환."""
    current  = await fetch_current_rainfall(lat, lon)
    forecast = await fetch_forecast_rainfall(lat, lon)

    if current < 0:
        return None  # 실패 시 caller가 fallback 처리

    r_1h = forecast["1h"] if forecast else current * random.uniform(0.9, 1.2)
    r_3h = forecast["3h"] if forecast else current * random.uniform(0.8, 1.3)
    return {"current": current, "1h": round(r_1h, 1), "3h": round(r_3h, 1), "source": "kma"}


async def fetch_seoul_rainfall() -> Dict[str, Any]:
    result = await fetch_city_rainfall(SEOUL_LAT, SEOUL_LON)
    if result is None:
        return _dummy_seoul()
    logger.info(f"KMA 서울 강수: 현재={result['current']}mm  1h={result['1h']}mm  3h={result['3h']}mm")
    return result


async def fetch_incheon_rainfall() -> Dict[str, Any]:
    result = await fetch_city_rainfall(INCHEON_LAT, INCHEON_LON)
    if result is None:
        return _dummy_seoul()
    logger.info(f"KMA 인천 강수: 현재={result['current']}mm  1h={result['1h']}mm  3h={result['3h']}mm")
    return result


async def fetch_grid_rainfall_batch(
    districts_meta: List[Dict[str, Any]],
    max_concurrent: int = 10,
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    """
    동 목록의 KMA 격자별 강수량을 병렬로 조회.
    서울 ~25개 / 인천 ~40개 격자를 중복 제거 후 배치 요청.

    Returns: {(nx, ny): {"current": float, "1h": float, "3h": float, "source": "kma"}}
    KMA_API_KEY 없으면 빈 dict 반환 → caller가 더미로 대체.
    """
    if not KMA_API_KEY:
        return {}

    # 고유 격자 수집 (격자 → 대표 좌표)
    grid_to_latlon: Dict[Tuple[int, int], Tuple[float, float]] = {}
    for d in districts_meta:
        key = _latlon_to_grid(d["lat"], d["lon"])
        if key not in grid_to_latlon:
            grid_to_latlon[key] = (d["lat"], d["lon"])

    logger.info(f"KMA 격자 조회: 동 {len(districts_meta)}개 → 고유 격자 {len(grid_to_latlon)}개")

    sem = asyncio.Semaphore(max_concurrent)

    async def _fetch_one(key: Tuple[int, int], lat: float, lon: float):
        async with sem:
            result = await fetch_city_rainfall(lat, lon)
        return key, result

    tasks = [_fetch_one(k, lat, lon) for k, (lat, lon) in grid_to_latlon.items()]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    grid_data: Dict[Tuple[int, int], Dict[str, Any]] = {}
    ok = 0
    for res in raw:
        if isinstance(res, Exception):
            logger.debug(f"격자 조회 예외: {res}")
            continue
        key, rainfall = res
        if rainfall is not None:
            grid_data[key] = rainfall
            ok += 1

    logger.info(f"KMA 격자 조회 완료: {ok}/{len(grid_to_latlon)} 격자 성공")
    return grid_data


def _dummy_seoul() -> Dict[str, Any]:
    """KMA 실패 시 더미 강수량 (현실적 분포)."""
    rng = random.Random(int(datetime.now().timestamp() / 600))
    roll = rng.random()
    if roll < 0.60:
        base = rng.uniform(0.0, 5.0)
    elif roll < 0.82:
        base = rng.uniform(5.0, 15.0)
    elif roll < 0.93:
        base = rng.uniform(15.0, 35.0)
    else:
        base = rng.uniform(35.0, 70.0)
    return {
        "current": round(base, 1),
        "1h":      round(base * rng.uniform(0.85, 1.25), 1),
        "3h":      round(base * rng.uniform(0.75, 1.35), 1),
        "source":  "dummy",
    }

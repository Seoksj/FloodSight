"""
한강홍수통제소 Open API 클라이언트.
API_KEY 환경변수 없으면 더미 데이터 자동 반환.

Base URL: https://api.hrfco.go.kr/{API_KEY}
  수위   : /waterlevel/list/10M.xml
  강수량 : /rainfall/list/10M.xml
  홍수예보: /fldfct/list.xml
"""

import os
import random
import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

API_KEY = os.getenv("HRFCO_API_KEY", "")
BASE_URL = f"https://api.hrfco.go.kr/{API_KEY}"

# 서울·인천 권역 주요 수위 관측소 (표준수문DB API 실측 ID)
_STATION_META: List[Dict[str, Any]] = [
    {"station_id": "1018683", "name": "한강대교",   "lat": 37.517, "lon": 126.997, "alert_level": 6.20},
    {"station_id": "1018661", "name": "팔당",        "lat": 37.530, "lon": 127.466, "alert_level": 5.50},
    {"station_id": "1018650", "name": "한강(행주)",  "lat": 37.613, "lon": 126.821, "alert_level": 5.00},
    {"station_id": "1018640", "name": "한강(청담)",  "lat": 37.519, "lon": 127.063, "alert_level": 6.00},
    {"station_id": "1017690", "name": "안양천",      "lat": 37.465, "lon": 126.882, "alert_level": 4.00},
    {"station_id": "1021670", "name": "중랑천",      "lat": 37.562, "lon": 127.088, "alert_level": 4.50},
    {"station_id": "1021650", "name": "중랑천(상)",  "lat": 37.618, "lon": 127.081, "alert_level": 3.50},
    {"station_id": "1019651", "name": "북한강",      "lat": 37.753, "lon": 127.468, "alert_level": 4.80},
]


def _random_station(meta: Dict) -> Dict:
    """관측소 메타 + 랜덤 수치 결합."""
    rng = random.Random()
    wl = round(rng.uniform(0.5, meta["alert_level"] * 1.1), 2)
    return {
        "station_id":  meta["station_id"],
        "name":        meta["name"],
        "lat":         meta["lat"],
        "lon":         meta["lon"],
        "water_level": wl,
        "alert_level": meta["alert_level"],
        "rainfall_1h": round(rng.uniform(0, 25), 1),
    }


def _dummy_stations() -> List[Dict]:
    return [_random_station(m) for m in _STATION_META]


def _parse_waterlevel_xml(xml_bytes: bytes) -> Dict[str, float]:
    """수위 XML → {station_id: water_level}."""
    root = ET.fromstring(xml_bytes)
    result = {}
    for item in root.iter("Waterlevel"):
        sid = (item.findtext("wlobscd") or "").strip()
        wl  = item.findtext("wl")
        if sid and wl:
            try:
                result[sid] = float(wl)
            except ValueError:
                pass
    return result


def _parse_rainfall_xml(xml_bytes: bytes) -> Dict[str, Dict]:
    """강수량 XML → {station_id: {1h}}. rfobscd는 8자리."""
    root = ET.fromstring(xml_bytes)
    result = {}
    for item in root.iter("Rainfall"):
        sid = (item.findtext("rfobscd") or "").strip()
        rf  = item.findtext("rf") or "0"
        if sid:
            try:
                result[sid] = {"rainfall_1h": float(rf)}
            except ValueError:
                pass
    return result


async def fetch_stations() -> List[Dict]:
    """
    HRFCO API에서 수위 + 강수량 조회.
    API_KEY 없으면 더미 데이터 반환.
    """
    if not API_KEY:
        logger.debug("HRFCO_API_KEY 미설정 → 더미 데이터 반환")
        return _dummy_stations()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            wl_resp = await client.get(f"{BASE_URL}/waterlevel/list/10M.xml")
            rf_resp = await client.get(f"{BASE_URL}/rainfall/list/10M.xml")

        wl_data = _parse_waterlevel_xml(wl_resp.content)
        rf_data = _parse_rainfall_xml(rf_resp.content)

        stations = []
        for meta in _STATION_META:
            sid = meta["station_id"]
            row = {
                "station_id":  sid,
                "name":        meta["name"],
                "lat":         meta["lat"],
                "lon":         meta["lon"],
                "alert_level": meta["alert_level"],
                "water_level": wl_data.get(sid, 0.0),
                "rainfall_1h": rf_data.get(sid, {}).get("rainfall_1h", 0.0),
                "_source":     "hrfco" if sid in wl_data else "missing",
            }
            stations.append(row)
        return stations

    except Exception as e:
        logger.warning(f"HRFCO API 호출 실패: {e} → 더미 데이터 사용")
        return _dummy_stations()


async def fetch_flood_forecast() -> List[Dict]:
    """홍수예보 조회. API_KEY 없으면 빈 리스트."""
    if not API_KEY:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}/fldfct/list.xml")
        root = ET.fromstring(resp.content)
        forecasts = []
        for item in root.iter("item"):
            forecasts.append({
                "station_id": (item.findtext("obscd") or "").strip(),
                "level":      (item.findtext("fldlvl") or "").strip(),
                "issued_at":  (item.findtext("fcttime") or "").strip(),
            })
        return forecasts
    except Exception as e:
        logger.warning(f"홍수예보 조회 실패: {e}")
        return []

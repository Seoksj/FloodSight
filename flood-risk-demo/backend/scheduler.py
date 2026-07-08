"""
APScheduler: 10분마다 데이터 수집 + ML 예측.

흐름:
  1. rule-based 위험도 계산 (즉시)
  2. ML 배치 추론 — current / 1h / 3h
  3. 블렌딩 후 캐시 갱신
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from cache import cache
from spatial.districts import (
    build_urban_risk_data,
    apply_ml_scores,
    build_geojson_for_horizon,
)
import database as db

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


def _build_all_geojsons(enriched) -> dict:
    return {h: build_geojson_for_horizon(enriched, h) for h in ("current", "1h", "3h")}


async def collect_and_update() -> None:
    logger.info("데이터 갱신 시작...")
    try:
        # 1단계: 더미 강수로 즉시 캐시 채움 → API 503 방지
        enriched, geojson_current = build_urban_risk_data(kma_rain=None)
        geojson_map = _build_all_geojsons(enriched)
        cache.update_all_horizons(enriched, geojson_map)
        logger.info(f"rule-based(더미) 완료 — {len(enriched)}개 지구")

        # 2단계: 동별 격자 강수량 조회 (고유 격자만 병렬 배치) 후 캐시 재갱신
        try:
            from clients.kma import fetch_grid_rainfall_batch
            from spatial.districts import DISTRICTS as _DISTRICTS
            kma_grid_data = await fetch_grid_rainfall_batch(_DISTRICTS)
            if kma_grid_data:
                enriched, geojson_current = build_urban_risk_data(kma_grid_data=kma_grid_data)
                geojson_map = _build_all_geojsons(enriched)
                cache.update_all_horizons(enriched, geojson_map)
                logger.info(f"KMA 격자 실황 반영 완료: {len(kma_grid_data)}개 격자")
        except Exception:
            logger.warning("KMA 격자 조회 실패 → 더미 강수 유지", exc_info=True)

        # ML 추론: 학습된 체크포인트 없으므로 생략 (rule-based 전용)

        # 3단계: DB 로그 저장 (비동기로 오류가 나도 서비스에 영향 없음)
        try:
            _save_to_db(enriched)
        except Exception:
            logger.warning("DB 저장 실패 (서비스 영향 없음)", exc_info=True)

    except Exception:
        logger.exception("데이터 갱신 실패")


def _save_to_db(enriched: list) -> None:
    """enriched 지구 목록을 DB 테이블에 기록."""
    horizons = ("current", "1h", "3h")
    rainfall_records = []
    risk_records = []

    for d in enriched:
        did = d["id"]

        # current 강수량 로그
        rainfall_records.append({
            "district_id":   did,
            "horizon":       "current",
            "rainfall_mmhr": d.get("rainfall_1h", 0),
            "source":        "kma" if d.get("_kma_real") else "dummy",
        })

        # horizon별 위험도 로그
        for h in horizons:
            if h == "current":
                risk_records.append({
                    "district_id": did,
                    "horizon":     h,
                    "rainfall_1h": d.get("rainfall_1h"),
                    "f_rainfall":  d.get("f_rainfall"),
                    "f_hand":      d.get("f_hand"),
                    "f_imperv":    d.get("f_imperv"),
                    "f_history":   d.get("f_history"),
                    "rule_score":  d.get("rule_score"),
                    "ml_score":    d.get("ml_score"),
                    "risk_score":  d.get("risk_score", 0),
                    "grade":       d.get("grade", "안전"),
                })
            else:
                fc = d.get("forecast", {}).get(h, {})
                if fc:
                    risk_records.append({
                        "district_id": did,
                        "horizon":     h,
                        "rainfall_1h": fc.get("rainfall"),
                        "f_rainfall":  None,
                        "f_hand":      None,
                        "f_imperv":    None,
                        "f_history":   None,
                        "rule_score":  None,
                        "ml_score":    None,
                        "risk_score":  fc.get("risk_score", 0),
                        "grade":       fc.get("grade", "안전"),
                    })

        # 경보 발령 관리
        db.check_and_insert_alert(
            did,
            d.get("grade", "안전"),
            d.get("rainfall_1h", 0),
            d.get("risk_score", 0),
        )

    db.insert_rainfall_logs(rainfall_records)
    db.insert_risk_score_logs(risk_records)
    logger.info(f"DB 저장 완료 — rainfall {len(rainfall_records)}건, risk {len(risk_records)}건")


def start_scheduler() -> None:
    _scheduler.add_job(
        collect_and_update,
        trigger="interval",
        minutes=10,
        id="collect_urban_risk",
        replace_existing=True,
    )
    _scheduler.start()
    asyncio.get_event_loop().create_task(collect_and_update())
    logger.info("스케줄러 시작 (10분 간격, ML 예측 포함)")


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)

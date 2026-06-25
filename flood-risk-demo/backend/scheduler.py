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

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


def _build_all_geojsons(enriched) -> dict:
    return {h: build_geojson_for_horizon(enriched, h) for h in ("current", "1h", "3h")}


async def collect_and_update() -> None:
    logger.info("데이터 갱신 시작...")
    try:
        # 1단계: rule-based 즉시 계산 → 캐시에 먼저 올려 API 응답 가능하게 함
        enriched, geojson_current = build_urban_risk_data()
        geojson_map = _build_all_geojsons(enriched)
        cache.update_all_horizons(enriched, geojson_map)
        logger.info(f"rule-based 완료 — {len(enriched)}개 지구")

        # 2단계: ML 배치 추론 (백그라운드)
        try:
            from predictor import predict_all_horizons
            ml_scores = await asyncio.get_event_loop().run_in_executor(
                None, predict_all_horizons, enriched
            )
            if ml_scores:
                enriched = apply_ml_scores(enriched, ml_scores)
                geojson_map = _build_all_geojsons(enriched)
                cache.update_all_horizons(enriched, geojson_map)
                logger.info("ML 블렌딩 완료")
        except Exception:
            logger.warning("ML 추론 스킵 — rule-based 결과 유지", exc_info=True)

    except Exception:
        logger.exception("데이터 갱신 실패")


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

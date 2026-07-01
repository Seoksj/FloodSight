"""
SQLite DB 초기화 및 CRUD 헬퍼.

테이블 구성:
  district          — 행정동 마스터 (정적)
  hrfco_station     — HRFCO 수위 관측소 마스터
  rainfall_log      — KMA 강수량 수집 이력
  water_level_log   — HRFCO 수위 수집 이력
  risk_score_log    — 10분 주기 위험도 계산 결과
  alert_log         — 경보 발령/해제 기록
  backtest_event    — 과거 침수 이벤트 (검증용)
  backtest_rainfall — 이벤트별 실측 강수 + 침수 여부
"""

import os
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "floodsight.db")


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ─────────────────────────────────────────────────────
# DDL
# ─────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS district (
    district_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    gu                  TEXT NOT NULL,
    city                TEXT NOT NULL,
    lat                 REAL NOT NULL,
    lon                 REAL NOT NULL,
    drainage_capacity   REAL NOT NULL,   -- mm/hr
    hand_value          REAL NOT NULL,   -- 지형 취약도 0~1
    impervious_ratio    REAL NOT NULL,   -- 불투수율 0~1
    flood_history_score REAL NOT NULL,   -- 침수 이력 지수 0~1
    boundary_geojson    TEXT,            -- GeoJSON Polygon 좌표 (JSON 문자열)
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE TABLE IF NOT EXISTS hrfco_station (
    station_code  TEXT PRIMARY KEY,
    station_name  TEXT NOT NULL,
    river_name    TEXT,
    lat           REAL,
    lon           REAL
);

CREATE TABLE IF NOT EXISTS rainfall_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    district_id   TEXT NOT NULL REFERENCES district(district_id),
    observed_at   TEXT NOT NULL,   -- ISO-8601 UTC
    horizon       TEXT NOT NULL CHECK (horizon IN ('current','1h','3h')),
    rainfall_mmhr REAL NOT NULL,
    source        TEXT NOT NULL DEFAULT 'dummy'  -- 'kma' | 'dummy'
);

CREATE TABLE IF NOT EXISTS water_level_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    station_code  TEXT NOT NULL REFERENCES hrfco_station(station_code),
    observed_at   TEXT NOT NULL,
    water_level_m REAL,
    rainfall_mm   REAL
);

CREATE TABLE IF NOT EXISTS risk_score_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    district_id   TEXT NOT NULL REFERENCES district(district_id),
    computed_at   TEXT NOT NULL,
    horizon       TEXT NOT NULL CHECK (horizon IN ('current','1h','3h')),
    rainfall_1h   REAL,
    f_rainfall    REAL,   -- 강수초과율 기여도
    f_hand        REAL,   -- 지형 취약도 기여도
    f_imperv      REAL,   -- 불투수율 기여도
    f_history     REAL,   -- 침수이력 기여도
    rule_score    REAL,
    ml_score      REAL,   -- NULL: 체크포인트 없음
    risk_score    REAL NOT NULL,
    grade         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    district_id   TEXT NOT NULL REFERENCES district(district_id),
    triggered_at  TEXT NOT NULL,
    grade         TEXT NOT NULL,
    rainfall_1h   REAL,
    risk_score    REAL,
    resolved_at   TEXT   -- NULL이면 현재 발령 중
);

CREATE TABLE IF NOT EXISTS backtest_event (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    event_start   TEXT NOT NULL,
    event_end     TEXT NOT NULL,
    description   TEXT
);

CREATE TABLE IF NOT EXISTS backtest_rainfall (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER NOT NULL REFERENCES backtest_event(event_id),
    district_id     TEXT NOT NULL REFERENCES district(district_id),
    recorded_at     TEXT NOT NULL,
    rainfall_mmhr   REAL NOT NULL,
    actually_flooded INTEGER NOT NULL DEFAULT 0  -- 0/1 boolean
);

CREATE INDEX IF NOT EXISTS idx_rainfall_log_district   ON rainfall_log(district_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_risk_score_district     ON risk_score_log(district_id, computed_at);
CREATE INDEX IF NOT EXISTS idx_alert_log_district      ON alert_log(district_id, triggered_at);
CREATE INDEX IF NOT EXISTS idx_backtest_rf_event       ON backtest_rainfall(event_id, district_id);
"""


def init_db() -> None:
    """DB 파일 없으면 생성, 테이블 DDL 실행."""
    with _conn() as con:
        con.executescript(_DDL)
    logger.info(f"DB 초기화 완료: {DB_PATH}")


# ─────────────────────────────────────────────────────
# district 마스터 CRUD
# ─────────────────────────────────────────────────────

def upsert_districts(districts: List[Dict[str, Any]]) -> None:
    """districts.py 의 DISTRICTS 리스트를 DB에 동기화."""
    import json
    now = _utcnow()
    with _conn() as con:
        for d in districts:
            boundary = json.dumps(d.get("boundary")) if d.get("boundary") else None
            con.execute("""
                INSERT INTO district
                    (district_id, name, gu, city, lat, lon,
                     drainage_capacity, hand_value, impervious_ratio,
                     flood_history_score, boundary_geojson, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(district_id) DO UPDATE SET
                    name=excluded.name,
                    gu=excluded.gu,
                    city=excluded.city,
                    lat=excluded.lat,
                    lon=excluded.lon,
                    drainage_capacity=excluded.drainage_capacity,
                    hand_value=excluded.hand_value,
                    impervious_ratio=excluded.impervious_ratio,
                    flood_history_score=excluded.flood_history_score,
                    boundary_geojson=excluded.boundary_geojson,
                    updated_at=excluded.updated_at
            """, (
                d["id"], d["name"], d["gu"], d["city"],
                d["lat"], d["lon"],
                d.get("drainage_capacity", 50.0),
                d.get("topo_depression", 0.5),
                d.get("impervious_ratio", 0.7),
                d.get("flood_history", 0.5),
                boundary, now,
            ))
    logger.info(f"district 마스터 {len(districts)}개 upsert 완료")


def get_all_districts() -> List[Dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM district ORDER BY district_id").fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────
# rainfall_log
# ─────────────────────────────────────────────────────

def insert_rainfall_logs(records: List[Dict]) -> None:
    """
    records: [{"district_id": ..., "horizon": ..., "rainfall_mmhr": ..., "source": ...}]
    """
    now = _utcnow()
    with _conn() as con:
        con.executemany("""
            INSERT INTO rainfall_log (district_id, observed_at, horizon, rainfall_mmhr, source)
            VALUES (?, ?, ?, ?, ?)
        """, [
            (r["district_id"], now, r["horizon"], r["rainfall_mmhr"], r.get("source", "dummy"))
            for r in records
        ])


def get_rainfall_history(district_id: str, limit: int = 72) -> List[Dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT observed_at, horizon, rainfall_mmhr, source
            FROM rainfall_log
            WHERE district_id = ? AND horizon = 'current'
            ORDER BY observed_at DESC LIMIT ?
        """, (district_id, limit)).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────
# risk_score_log
# ─────────────────────────────────────────────────────

def insert_risk_score_logs(records: List[Dict]) -> None:
    """
    records: 각 지구 × 각 horizon 위험도 결과 딕셔너리 목록.
    """
    now = _utcnow()
    with _conn() as con:
        con.executemany("""
            INSERT INTO risk_score_log
                (district_id, computed_at, horizon,
                 rainfall_1h, f_rainfall, f_hand, f_imperv, f_history,
                 rule_score, ml_score, risk_score, grade)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, [
            (
                r["district_id"], now, r["horizon"],
                r.get("rainfall_1h"), r.get("f_rainfall"), r.get("f_hand"),
                r.get("f_imperv"), r.get("f_history"),
                r.get("rule_score"), r.get("ml_score"),
                r["risk_score"], r["grade"],
            )
            for r in records
        ])


def get_risk_history(district_id: str, horizon: str = "current", limit: int = 48) -> List[Dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT computed_at, horizon, risk_score, grade,
                   rainfall_1h, f_rainfall, f_hand, f_imperv, f_history,
                   rule_score, ml_score
            FROM risk_score_log
            WHERE district_id = ? AND horizon = ?
            ORDER BY computed_at DESC LIMIT ?
        """, (district_id, horizon, limit)).fetchall()
    return [dict(r) for r in rows]


def get_latest_risk_summary() -> List[Dict]:
    """각 지구의 현재(current) 최신 위험도 한 건씩."""
    with _conn() as con:
        rows = con.execute("""
            SELECT r.district_id, d.name, d.gu, d.city,
                   r.computed_at, r.risk_score, r.grade, r.rainfall_1h
            FROM risk_score_log r
            JOIN district d ON d.district_id = r.district_id
            WHERE r.horizon = 'current'
              AND r.computed_at = (
                  SELECT MAX(r2.computed_at) FROM risk_score_log r2
                  WHERE r2.district_id = r.district_id AND r2.horizon = 'current'
              )
            ORDER BY r.risk_score DESC
        """).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────
# alert_log
# ─────────────────────────────────────────────────────

def check_and_insert_alert(district_id: str, grade: str,
                            rainfall_1h: float, risk_score: float) -> None:
    """경보·위험 등급이면 미해제 경보가 없을 때만 신규 발령 기록."""
    if grade not in ("경보", "위험"):
        _resolve_alert(district_id)
        return
    now = _utcnow()
    with _conn() as con:
        existing = con.execute("""
            SELECT id FROM alert_log
            WHERE district_id = ? AND resolved_at IS NULL
        """, (district_id,)).fetchone()
        if not existing:
            con.execute("""
                INSERT INTO alert_log (district_id, triggered_at, grade, rainfall_1h, risk_score)
                VALUES (?,?,?,?,?)
            """, (district_id, now, grade, rainfall_1h, risk_score))


def _resolve_alert(district_id: str) -> None:
    now = _utcnow()
    with _conn() as con:
        con.execute("""
            UPDATE alert_log SET resolved_at = ?
            WHERE district_id = ? AND resolved_at IS NULL
        """, (now, district_id))


def get_active_alerts() -> List[Dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT a.id, a.district_id, d.name, d.gu, d.city,
                   a.triggered_at, a.grade, a.rainfall_1h, a.risk_score
            FROM alert_log a
            JOIN district d ON d.district_id = a.district_id
            WHERE a.resolved_at IS NULL
            ORDER BY a.triggered_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_alert_history(limit: int = 50) -> List[Dict]:
    with _conn() as con:
        rows = con.execute("""
            SELECT a.id, a.district_id, d.name, d.gu,
                   a.triggered_at, a.resolved_at, a.grade, a.rainfall_1h, a.risk_score
            FROM alert_log a
            JOIN district d ON d.district_id = a.district_id
            ORDER BY a.triggered_at DESC LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────
# backtest
# ─────────────────────────────────────────────────────

def seed_backtest_event() -> None:
    """2022-08-08 강남역 집중호우 이벤트 초기 데이터 삽입."""
    with _conn() as con:
        exists = con.execute(
            "SELECT 1 FROM backtest_event WHERE name = ?", ("2022-08-08 강남역 집중호우",)
        ).fetchone()
        if exists:
            return

        con.execute("""
            INSERT INTO backtest_event (name, event_start, event_end, description)
            VALUES (?,?,?,?)
        """, (
            "2022-08-08 강남역 집중호우",
            "2022-08-08T18:00:00Z",
            "2022-08-09T06:00:00Z",
            "2022년 8월 8일 수도권 집중호우. 강남역 일대 141.5mm/hr 기록, "
            "서초·강남·동작·관악구 침수 피해.",
        ))
        event_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]

        # 주요 피해 지구 실측 데이터 (문헌 기반)
        records = [
            ("SL01", "2022-08-08T20:00:00Z", 141.5, 1),
            ("SL01", "2022-08-08T21:00:00Z", 98.3,  1),
            ("SL02", "2022-08-08T20:00:00Z", 120.0, 1),
            ("SL02", "2022-08-08T21:00:00Z", 85.0,  1),
            ("SL03", "2022-08-08T20:00:00Z", 95.0,  1),
            ("SL03", "2022-08-08T21:00:00Z", 70.0,  0),
            ("SL06", "2022-08-08T20:00:00Z", 88.0,  1),
            ("SL10", "2022-08-08T20:00:00Z", 72.0,  0),
        ]
        con.executemany("""
            INSERT INTO backtest_rainfall (event_id, district_id, recorded_at, rainfall_mmhr, actually_flooded)
            VALUES (?,?,?,?,?)
        """, [(event_id, *r) for r in records])
    logger.info("backtest_event 초기 데이터 삽입 완료")


def get_backtest_events() -> List[Dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM backtest_event ORDER BY event_start DESC").fetchall()
    return [dict(r) for r in rows]


def get_backtest_detail(event_id: int) -> Dict:
    with _conn() as con:
        event = con.execute(
            "SELECT * FROM backtest_event WHERE event_id = ?", (event_id,)
        ).fetchone()
        if not event:
            return {}
        rows = con.execute("""
            SELECT br.district_id, d.name, d.gu, br.recorded_at,
                   br.rainfall_mmhr, br.actually_flooded
            FROM backtest_rainfall br
            JOIN district d ON d.district_id = br.district_id
            WHERE br.event_id = ?
            ORDER BY br.recorded_at, br.rainfall_mmhr DESC
        """, (event_id,)).fetchall()
    return {"event": dict(event), "records": [dict(r) for r in rows]}


# ─────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────

def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

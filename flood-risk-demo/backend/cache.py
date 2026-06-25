"""
Thread-safe in-memory cache for latest station data and risk GeoJSON.
"""

import threading
from datetime import datetime
from typing import List, Dict, Any, Optional


class DataCache:
    def __init__(self):
        self._lock = threading.RLock()
        self._stations: List[Dict[str, Any]] = []
        self._geojson: Dict[str, Optional[Dict]] = {"current": None, "1h": None, "3h": None}
        self._last_updated: Optional[datetime] = None

    def update(self, stations: List[Dict], risk_geojson: Dict, horizon: str = "current") -> None:
        with self._lock:
            self._stations = stations
            self._geojson[horizon] = risk_geojson
            self._last_updated = datetime.utcnow()

    def update_all_horizons(self, stations: List[Dict], geojson_map: Dict[str, Dict]) -> None:
        with self._lock:
            self._stations = stations
            for h, gj in geojson_map.items():
                self._geojson[h] = gj
            self._last_updated = datetime.utcnow()

    @property
    def stations(self) -> List[Dict]:
        with self._lock:
            return list(self._stations)

    def get_geojson(self, horizon: str = "current") -> Optional[Dict]:
        with self._lock:
            return self._geojson.get(horizon)

    @property
    def risk_geojson(self) -> Optional[Dict]:
        with self._lock:
            return self._geojson.get("current")

    @property
    def last_updated(self) -> Optional[datetime]:
        with self._lock:
            return self._last_updated

    @property
    def is_ready(self) -> bool:
        with self._lock:
            return self._geojson.get("current") is not None


cache = DataCache()

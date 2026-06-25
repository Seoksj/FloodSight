"""
Overpass API로 36개 침수 취약 지구 실제 행정동 경계 폴리곤 수집.
결과: backend/spatial/district_boundaries.json

사용법:
  python scripts/fetch_boundaries.py
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

CITY_META = {
    "서울":  {"parent": "서울특별시", "p_level": "4"},
    "인천":  {"parent": "인천광역시", "p_level": "4"},
    "부산":  {"parent": "부산광역시", "p_level": "4"},
    "대구":  {"parent": "대구광역시", "p_level": "4"},
    "광주":  {"parent": "광주광역시", "p_level": "4"},
    "대전":  {"parent": "대전광역시", "p_level": "4"},
    "수원":  {"parent": "경기도", "p_level": "4", "c_level": "5", "city_name": "수원시"},
    "성남":  {"parent": "경기도", "p_level": "4", "c_level": "5", "city_name": "성남시"},
    "부천":  {"parent": "경기도", "p_level": "4", "c_level": "5", "city_name": "부천시"},
}

# OSM 이름이 다른 경우 직접 지정 (조사 결과 반영)
# "원래이름": ["시도할 OSM 이름들"]
FALLBACK_NAMES = {
    "천호동":  ["천호1동","천호2동","천호3동"],
    "여의도동":["여의도동"],   # 법정동 → 행정동 불일치 가능
    "봉천동":  ["봉천10동","봉천11동","봉천1동","봉천2동"],
    "목동":    ["목1동","목2동","목3동","목4동","목5동"],
    "개봉동":  ["개봉1동","개봉2동","개봉3동"],
    "도봉동":  ["도봉1동","도봉2동"],
    "부평2동": ["부평2동"],
    "온천4동": ["온천4동"],
    "서동":    ["서1동","서2동","서3동","서동"],
    "하단동":  ["하단1동","하단2동"],
    "농성동":  ["농성1동","농성2동"],
    "봉명동":  ["봉명동","봉명1동","봉명2동"],
    "인계동":  ["인계동"],
    "금광동":  ["금광1동","금광2동"],
    "중동":    ["중1동","중2동","중3동"],
    "신도림동":["신도림동"],
    "화곡8동": ["화곡8동"],
    "상도3동": ["상도3동"],
    "불광2동": ["불광2동"],
    "범천동":  ["범천1동","범천2동","범천동"],
}


def build_query(city: str, gu: str, name: str) -> str:
    meta = CITY_META[city]
    p_name  = meta["parent"]
    p_level = meta["p_level"]
    c_level = meta.get("c_level")
    c_name  = meta.get("city_name")

    if c_level:
        return f"""[out:json][timeout:30];
area["name"="{p_name}"]["admin_level"="{p_level}"]->.prov;
area["name"="{c_name}"]["admin_level"="{c_level}"](area.prov)->.city;
area["name"="{gu}"]["admin_level"="6"](area.city)->.gu;
relation["name"="{name}"]["admin_level"="8"]["boundary"="administrative"](area.gu);
out geom;"""
    else:
        return f"""[out:json][timeout:30];
area["name"="{p_name}"]["admin_level"="{p_level}"]->.city;
area["name"="{gu}"]["admin_level"="6"](area.city)->.gu;
relation["name"="{name}"]["admin_level"="8"]["boundary"="administrative"](area.gu);
out geom;"""


def fetch_overpass(query: str, retries: int = 3) -> dict:
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(OVERPASS_URL, data=data, headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent":   "FloodSight/1.0 (flood risk monitoring demo)",
                "Accept":       "application/json",
            })
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                wait = 8 * (attempt + 1)
                print(f"429 rate limit, {wait}초 대기...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise
    return {}


def chain_ways(outer_ways: list) -> list | None:
    def pts(way):
        return [(round(g["lon"], 6), round(g["lat"], 6)) for g in way.get("geometry", [])]

    segments = [pts(w) for w in outer_ways if pts(w)]
    if not segments:
        return None

    ring = list(segments[0])
    used = {0}

    for _ in range(len(segments) - 1):
        tail = ring[-1]
        found = False
        for i, seg in enumerate(segments):
            if i in used:
                continue
            if abs(seg[0][0] - tail[0]) < 1e-6 and abs(seg[0][1] - tail[1]) < 1e-6:
                ring.extend(seg[1:])
                used.add(i); found = True; break
            if abs(seg[-1][0] - tail[0]) < 1e-6 and abs(seg[-1][1] - tail[1]) < 1e-6:
                ring.extend(list(reversed(seg))[1:])
                used.add(i); found = True; break
        if not found:
            break

    if len(ring) < 4:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def extract_polygon(data: dict) -> list | None:
    elements = data.get("elements", [])
    if not elements:
        return None
    members = elements[0].get("members", [])
    outer   = [m for m in members if m.get("type") == "way" and m.get("role") == "outer"]
    if not outer:
        return None
    ring = chain_ways(outer)
    return [ring] if ring else None


def try_fetch(city: str, gu: str, name: str) -> tuple[list | None, str | None]:
    """이름 변형을 순서대로 시도. (polygon, matched_name) 반환."""
    candidates = [name] + FALLBACK_NAMES.get(name, [])
    # 중복 제거하면서 순서 유지
    seen = set()
    uniq = []
    for n in candidates:
        if n not in seen:
            seen.add(n); uniq.append(n)

    for candidate in uniq:
        q = build_query(city, gu, candidate)
        data = fetch_overpass(q)
        poly = extract_polygon(data)
        if poly:
            return poly, candidate
        time.sleep(2)

    return None, None


def fetch_all(districts: list, existing: dict) -> dict:
    results = dict(existing)
    todo = [d for d in districts if d["id"] not in results]
    total = len(districts)

    print(f"미수집 {len(todo)}개 지구 처리\n")

    for i, d in enumerate(todo, 1):
        did  = d["id"]
        name = d["name"]
        city = d["city"]
        gu   = d["gu"]

        idx = districts.index(d) + 1
        print(f"[{idx:02d}/{total}] {city} {gu} {name} ...", end=" ", flush=True)

        try:
            poly, matched = try_fetch(city, gu, name)
            if poly:
                results[did] = poly
                label = f"'{matched}'" if matched != name else "OK"
                print(f"{label} ({len(poly[0])} pts)")
            else:
                print("NOT FOUND — 원형 폴백")
        except Exception as e:
            print(f"ERROR: {e}")

        time.sleep(2.5)

    return results


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
    from spatial.districts import DISTRICTS

    out_path = Path(__file__).parent.parent / "backend" / "spatial" / "district_boundaries.json"

    # 기존 결과 로드 (재실행 시 이미 수집된 것 건너뜀)
    existing = {}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
            print(f"기존 {len(existing)}개 로드\n")
        except Exception:
            pass

    boundaries = fetch_all(DISTRICTS, existing)

    out_path.write_text(json.dumps(boundaries, ensure_ascii=False, indent=2))
    print(f"\n완료: {len(boundaries)}/{len(DISTRICTS)}개 수집")
    print(f"저장: {out_path}")

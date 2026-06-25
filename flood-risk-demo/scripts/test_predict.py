"""
스크립트 2: /predict 엔드포인트 E2E 테스트.
Backend가 실행 중이어야 합니다 (uvicorn main:app --reload).

Usage:
  python scripts/test_predict.py [--url http://localhost:8000]
"""

import argparse
import os
import sys
import json

import httpx

SCRIPT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(SCRIPT_DIR, "test_data")


def find_file(name, extensions=(".tif", ".npy")):
    for ext in extensions:
        p = os.path.join(DATA_DIR, name + ext)
        if os.path.exists(p):
            return p
    return None


def main(base_url: str):
    sar_path = find_file("dummy_sar")
    dem_path = find_file("dummy_dem")

    if not sar_path or not dem_path:
        print("테스트 데이터가 없습니다. 먼저 실행하세요:")
        print("  python scripts/create_test_data.py")
        sys.exit(1)

    print(f"SAR: {sar_path}")
    print(f"DEM: {dem_path}")

    # Health check
    print(f"\n[1] GET {base_url}/health")
    r = httpx.get(f"{base_url}/health", timeout=10)
    print(f"  status: {r.status_code}")
    print(f"  body  : {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

    # Predict
    print(f"\n[2] POST {base_url}/predict")
    with open(sar_path, "rb") as sf, open(dem_path, "rb") as df:
        files = {
            "sar": ("dummy_sar.tif", sf, "application/octet-stream"),
            "dem": ("dummy_dem.tif", df, "application/octet-stream"),
        }
        data = {"precipitation": "최근 72시간 누적 강수량 250mm, 강도 시간당 45mm/h"}
        r = httpx.post(f"{base_url}/predict", files=files, data=data, timeout=60)

    print(f"  status: {r.status_code}")
    if r.status_code == 200:
        resp = r.json()
        prob_map = resp["prob_map"]
        H = len(prob_map)
        W = len(prob_map[0]) if H > 0 else 0
        print(f"  prob_map shape : [{H}][{W}]  (expected [256][256])")
        print(f"  risk_level     : {resp['risk_level']}")
        print(f"  stats          : {json.dumps(resp['stats'], indent=4)}")
        assert H == 256 and W == 256, f"Shape 불일치: [{H}][{W}]"
        print("\n[PASS] /predict 응답 검증 완료")
    else:
        print(f"  [FAIL] 응답: {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    main(args.url)

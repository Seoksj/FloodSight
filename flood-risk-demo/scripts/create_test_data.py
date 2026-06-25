"""
스크립트 1: 테스트용 dummy SAR/DEM GeoTIFF 생성.
rasterio가 없으면 numpy .npy 형식으로 저장 (backend가 fallback으로 읽을 수 있음).

Usage:
  python scripts/create_test_data.py
"""

import os
import numpy as np

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

H, W = 256, 256
rng = np.random.default_rng(42)


def make_sar(h, w):
    """VV, VH 채널 시뮬레이션 (dB 스케일: -30 ~ 0)"""
    vv = rng.normal(-12, 5, (h, w)).astype(np.float32)
    vh = rng.normal(-20, 4, (h, w)).astype(np.float32)
    return np.stack([vv, vh], axis=0)   # (2, H, W)


def make_dem(h, w):
    """단순 경사면 DEM + 노이즈 (단위: m)"""
    x = np.linspace(0, 200, w)
    y = np.linspace(0, 200, h)
    xx, yy = np.meshgrid(x, y)
    base = 500 - 1.5 * xx + 0.5 * yy
    noise = rng.normal(0, 10, (h, w))
    return (base + noise).astype(np.float32)[np.newaxis, ...]  # (1, H, W)


def save_geotiff(arr, path):
    try:
        import rasterio
        from rasterio.transform import from_bounds
        c, h, w = arr.shape
        transform = from_bounds(126.0, 37.0, 127.0, 38.0, w, h)
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=h,
            width=w,
            count=c,
            dtype=arr.dtype,
            crs="EPSG:4326",
            transform=transform,
        ) as ds:
            for i in range(c):
                ds.write(arr[i], i + 1)
        print(f"  [rasterio] {path}  shape={arr.shape}")
    except ImportError:
        # Fallback: numpy format (backend의 _read_geotiff_numpy 로 읽힘)
        npy_path = path.replace(".tif", ".npy")
        np.save(npy_path, arr)
        print(f"  [numpy fallback] {npy_path}  shape={arr.shape}")
        return npy_path
    return path


if __name__ == "__main__":
    print(f"테스트 데이터 생성: {OUTPUT_DIR}")

    sar = make_sar(H, W)
    dem = make_dem(H, W)

    sar_path = save_geotiff(sar, os.path.join(OUTPUT_DIR, "dummy_sar.tif"))
    dem_path = save_geotiff(dem, os.path.join(OUTPUT_DIR, "dummy_dem.tif"))

    print(f"\n생성 완료:")
    print(f"  SAR: shape={sar.shape}, min={sar.min():.2f}, max={sar.max():.2f}")
    print(f"  DEM: shape={dem.shape}, min={dem.min():.2f}, max={dem.max():.2f}")
    print("\n다음 명령으로 /predict 테스트:")
    print(f'  python scripts/test_predict.py')

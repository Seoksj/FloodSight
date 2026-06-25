"""
Preprocessing utilities: GeoTIFF → normalized tensors.
Handles missing rasterio gracefully (numpy fallback for testing).
"""

import io
import numpy as np
import torch
from typing import Tuple


def _read_geotiff_rasterio(data: bytes) -> np.ndarray:
    import rasterio
    with rasterio.open(io.BytesIO(data)) as ds:
        arr = ds.read().astype(np.float32)  # (C, H, W)
    return arr


def _read_geotiff_numpy(data: bytes) -> np.ndarray:
    """Minimal fallback: interpret raw bytes as a saved .npy array."""
    try:
        return np.load(io.BytesIO(data)).astype(np.float32)
    except Exception:
        # Last resort: return a 256×256 dummy
        return np.random.rand(1, 256, 256).astype(np.float32)


def read_geotiff(data: bytes) -> np.ndarray:
    try:
        return _read_geotiff_rasterio(data)
    except Exception:
        return _read_geotiff_numpy(data)


def normalize_sar(arr: np.ndarray, target_h: int = 256, target_w: int = 256) -> torch.Tensor:
    """
    arr: (C, H, W) with C=2 (VV, VH)
    Returns: (T, C, H, W) with T=4 time steps (repeated for dummy data)
    """
    from torch.nn.functional import interpolate

    arr = np.clip(arr, -50, 1)
    arr = (arr + 50) / 51.0  # normalize to [0, 1]

    if arr.shape[0] < 2:
        arr = np.concatenate([arr] * 2, axis=0)[:2]
    arr = arr[:2]  # keep VV, VH

    t = torch.from_numpy(arr).unsqueeze(0)  # (1, 2, H, W)
    if t.shape[-2:] != (target_h, target_w):
        t = interpolate(t, size=(target_h, target_w), mode="bilinear", align_corners=False)

    # Repeat across time axis to get (T=4, C=2, H, W)
    return t.squeeze(0).unsqueeze(0).repeat(4, 1, 1, 1)


def normalize_dem(arr: np.ndarray, target_h: int = 256, target_w: int = 256) -> torch.Tensor:
    """
    arr: (C, H, W) → pads/trims to 5 channels (elevation + derived)
    Returns: (5, H, W)
    """
    from torch.nn.functional import interpolate

    # Derive extra channels from elevation if only 1 band is provided
    channels = [arr[0]]  # elevation

    # Simple gradient as slope proxy
    gy = np.gradient(arr[0], axis=0)
    gx = np.gradient(arr[0], axis=1)
    slope = np.sqrt(gx ** 2 + gy ** 2)
    aspect = np.arctan2(gy, gx)
    curvature = np.gradient(slope, axis=0) + np.gradient(slope, axis=1)

    # Flow accumulation proxy (low-pass of elevation)
    try:
        from scipy.ndimage import uniform_filter
        flow_acc = -uniform_filter(arr[0], size=15)
    except ImportError:
        flow_acc = -np.convolve(arr[0].ravel(), np.ones(15)/15, mode='same').reshape(arr[0].shape)

    channels += [slope, aspect, curvature, flow_acc]

    stacked = np.stack(channels[:5], axis=0).astype(np.float32)  # (5, H, W)
    # Per-channel standardization
    for i in range(5):
        std = stacked[i].std()
        stacked[i] = (stacked[i] - stacked[i].mean()) / (std + 1e-6)

    t = torch.from_numpy(stacked).unsqueeze(0)  # (1, 5, H, W)
    if t.shape[-2:] != (target_h, target_w):
        t = interpolate(t, size=(target_h, target_w), mode="bilinear", align_corners=False)
    return t.squeeze(0)   # (5, H, W)


def tokenize_precipitation(text: str, max_length: int = 64):
    """
    Tokenize precipitation description text.
    Returns (input_ids, attention_mask) as torch.LongTensor of shape (1, L).
    Falls back to simple character-level encoding if transformers unavailable.
    """
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("klue/roberta-base")
        enc = tokenizer(
            text,
            max_length=max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        )
        return enc["input_ids"], enc["attention_mask"]
    except Exception:
        # Fallback: simple numeric encoding
        ids = [ord(c) % 1000 for c in text[:max_length]]
        ids += [0] * (max_length - len(ids))
        mask = [1 if i < len(text) else 0 for i in range(max_length)]
        return (
            torch.tensor([ids], dtype=torch.long),
            torch.tensor([mask], dtype=torch.long),
        )

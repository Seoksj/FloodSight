"""
Inference module with automatic dummy-predictor fallback.
"""

import io
import os
import logging
import numpy as np
import torch
from scipy.ndimage import gaussian_filter
from typing import Optional, Tuple, Dict, Any

from preprocess import read_geotiff, normalize_sar, normalize_dem, tokenize_precipitation

logger = logging.getLogger(__name__)

CHECKPOINT_PATH = os.getenv("MODEL_CHECKPOINT", "checkpoints/model.pt")
_model = None
_model_loaded = False


def _try_load_model():
    global _model, _model_loaded
    if not os.path.exists(CHECKPOINT_PATH):
        logger.warning(f"Checkpoint not found at {CHECKPOINT_PATH} — using dummy predictor")
        return

    try:
        from model import FloodRiskModel
        m = FloodRiskModel()
        state = torch.load(CHECKPOINT_PATH, map_location="cpu")
        m.load_state_dict(state)
        m.eval()
        _model = m
        _model_loaded = True
        logger.info("Model loaded from checkpoint")
    except Exception as e:
        logger.error(f"Model load failed: {e} — using dummy predictor")


def initialize():
    _try_load_model()


def get_model_status() -> Dict[str, Any]:
    return {
        "model_loaded": _model_loaded,
        "checkpoint_path": CHECKPOINT_PATH,
        "checkpoint_exists": os.path.exists(CHECKPOINT_PATH),
    }


# ---------------------------------------------------------------------------
# Dummy predictor
# ---------------------------------------------------------------------------

def _dummy_predict(H: int = 256, W: int = 256) -> np.ndarray:
    """
    Simulate a plausible flood probability map:
    random base + gaussian blobs + elevation-aware low-frequency signal.
    """
    base = np.random.rand(H, W).astype(np.float32) * 0.3
    # Add a few high-risk blobs
    for _ in range(np.random.randint(2, 5)):
        cy, cx = np.random.randint(0, H), np.random.randint(0, W)
        y, x = np.ogrid[:H, :W]
        r = np.random.randint(20, 60)
        mask = ((y - cy) ** 2 + (x - cx) ** 2) < r ** 2
        base[mask] += np.random.uniform(0.3, 0.6)

    prob = gaussian_filter(base, sigma=np.random.uniform(8, 20))
    return np.clip(prob, 0, 1).astype(np.float32)


# ---------------------------------------------------------------------------
# Real predictor
# ---------------------------------------------------------------------------

def _model_predict(
    sar_arr: np.ndarray,
    dem_arr: np.ndarray,
    precipitation_text: str,
    H: int = 256,
    W: int = 256,
) -> np.ndarray:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _model.to(device)

    sar_t = normalize_sar(sar_arr, H, W).unsqueeze(0).to(device)   # (1, T, C, H, W)
    dem_t = normalize_dem(dem_arr, H, W).unsqueeze(0).to(device)   # (1, 5, H, W)
    ids, mask = tokenize_precipitation(precipitation_text)
    ids = ids.to(device)
    mask = mask.to(device)

    with torch.no_grad():
        prob = _model(sar_t, dem_t, ids, mask)  # (1, 1, H, W)

    return prob.squeeze().cpu().numpy()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def predict(
    sar_bytes: bytes,
    dem_bytes: bytes,
    precipitation_text: str,
    target_h: int = 256,
    target_w: int = 256,
) -> Tuple[np.ndarray, str, Dict[str, float]]:
    """
    Returns (prob_map [H,W], risk_level, stats).
    """
    if _model_loaded:
        sar_arr = read_geotiff(sar_bytes)
        dem_arr = read_geotiff(dem_bytes)
        prob_map = _model_predict(sar_arr, dem_arr, precipitation_text, target_h, target_w)
    else:
        prob_map = _dummy_predict(target_h, target_w)

    max_prob = float(prob_map.max())
    mean_prob = float(prob_map.mean())
    high_risk_pct = float((prob_map > 0.5).mean() * 100)

    if max_prob > 0.75:
        risk_level = "HIGH"
    elif max_prob > 0.5:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    stats = {
        "max_prob": round(max_prob, 4),
        "mean_prob": round(mean_prob, 4),
        "high_risk_pct": round(high_risk_pct, 2),
    }

    return prob_map, risk_level, stats

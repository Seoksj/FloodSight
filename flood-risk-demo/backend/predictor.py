"""
지구별 단기 침수 위험 ML 예측 모듈.

입력  : 36개 지구 메타 + 현재/예보 강수량
출력  : district_id → {current, 1h, 3h} ML 기반 위험도 스코어

데이터 생성 원리
  SAR 프록시 : 강수량 ↑ → VV 후방산란 ↓ (수면 reflection), VH 노이즈 ↑
  DEM 프록시 : topo_depression → 중심부가 낮은 bowl형 고도 텐서
  텍스트     : "현재 Xmm/hr, 1h 후 Ymm/hr, 3h 후 Zmm/hr" 형식

블렌딩 전략
  체크포인트 없음 : rule_score 0.65 + ml_score 0.35
  체크포인트 있음 : rule_score 0.30 + ml_score 0.70
"""

import os
import logging
import numpy as np
from typing import List, Dict, Any, Optional

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    _TORCH_AVAILABLE = False

logger = logging.getLogger(__name__)

_model: Optional[Any] = None
_model_loaded = False   # 실제 체크포인트로 로드됐는지

H = W = 64   # 추론용 공간 해상도 (full 256보다 8x 빠름)
T = 4        # SAR 시간 스텝


# ──────────────────────────────────────────────────────────────
# 모델 로드 (싱글턴)
# ──────────────────────────────────────────────────────────────

def _load_model():
    global _model, _model_loaded
    if _model is not None:
        return
    if not _TORCH_AVAILABLE:
        logger.info("torch 미설치 — rule-based 전용 모드")
        return
    try:
        from model import FloodRiskModel
        m = FloodRiskModel(d_model=256, patch_size=16)
        ckpt = os.path.join(os.path.dirname(__file__), "checkpoints", "model.pt")
        if os.path.exists(ckpt):
            m.load_state_dict(torch.load(ckpt, map_location="cpu"))
            _model_loaded = True
            logger.info("체크포인트 로드 완료")
        m.eval()
        _model = m
        logger.info(f"예측 모델 준비 완료 (checkpoint={'있음' if _model_loaded else '없음(더미 가중치)'})")
    except Exception as e:
        logger.warning(f"모델 초기화 실패: {e}")
        _model = None


# ──────────────────────────────────────────────────────────────
# 프록시 데이터 생성
# ──────────────────────────────────────────────────────────────

def _rainfall_to_sar(rainfall_mm: float) -> torch.Tensor:
    """
    강수량(mm/hr) → 가상 SAR 텐서 (T, 2, H, W).

    물리적 근거:
      - 강수 증가 → 도로·지면에 수막 형성 → VV 후방산란 감소 (거울 반사)
      - 강수 증가 → 수면 거칠기 증가 → VH 노이즈 증가
    """
    rng = np.random.RandomState(int(rainfall_mm * 10) % 99991)
    # dB 스케일. 건조 시 VV≈-12, VH≈-20
    base_vv = max(-35.0, -12.0 - rainfall_mm * 0.28)
    base_vh = max(-45.0, -20.0 + rainfall_mm * 0.08)

    frames = []
    for t in range(T):
        # 시간 경과 → 점진적 변화 (침수 진행)
        factor = 1.0 + t * 0.05
        vv = (base_vv * factor + rng.normal(0, 2.5, (H, W))).clip(-50, 0)
        vh = (base_vh + rng.normal(0, 1.8, (H, W))).clip(-50, 0)
        frames.append(np.stack([vv, vh]).astype(np.float32))

    return torch.from_numpy(np.stack(frames)) if _TORCH_AVAILABLE else np.stack(frames)  # (T, 2, H, W)


def _district_to_dem(meta: Dict) -> torch.Tensor:
    """
    지구 취약도 메타 → 가상 DEM 텐서 (5, H, W).

    채널: [고도, 경사, 향, 곡률, 유량]
    topo_depression이 높을수록 중심부 고도가 낮은 bowl 형태.
    """
    dep = meta.get("topo_depression", 0.5)
    seed = int(dep * 100 + sum(ord(c) for c in meta.get("id", "X")))
    rng = np.random.RandomState(seed)

    yv, xv = np.meshgrid(
        np.linspace(-1, 1, W), np.linspace(-1, 1, H), indexing="ij"
    )
    r = np.sqrt(xv ** 2 + yv ** 2)

    base_elev = 80.0 - dep * 55.0             # 저지대일수록 낮은 기본 고도
    elev = base_elev + (1 - dep) * 45.0 * r   # bowl: 저지대는 중심이 낮음
    elev += rng.normal(0, 3.0, (H, W))

    slope = np.gradient(elev, axis=0) ** 2 + np.gradient(elev, axis=1) ** 2
    slope = np.sqrt(slope)
    aspect    = np.arctan2(np.gradient(elev, axis=1), np.gradient(elev, axis=0))
    curvature = np.gradient(slope, axis=0) + np.gradient(slope, axis=1)
    flow_acc  = -elev * dep   # 저지대일수록 유량 집중

    channels = np.stack([
        elev.astype(np.float32),
        slope.astype(np.float32),
        aspect.astype(np.float32),
        curvature.astype(np.float32),
        flow_acc.astype(np.float32),
    ])   # (5, H, W)

    # 채널별 표준화
    for i in range(5):
        std = channels[i].std()
        channels[i] = (channels[i] - channels[i].mean()) / (std + 1e-6)

    return torch.from_numpy(channels) if _TORCH_AVAILABLE else channels  # (5, H, W)


def _precip_text(name: str, r_cur: float, r_1h: float, r_3h: float) -> str:
    intensity = "집중호우" if r_1h > 50 else "강한 비" if r_1h > 30 else "보통 비"
    return (
        f"{name} 현재 강수 {r_cur:.0f}mm/hr. "
        f"1시간 후 예상 {r_1h:.0f}mm/hr. "
        f"3시간 후 예상 {r_3h:.0f}mm/hr. "
        f"{intensity} 예상. "
        f"{'도심 저지대 침수 위험.' if r_1h > 30 else '배수 용량 주시 필요.'}"
    )


def _tokenize(text: str, max_len: int = 64):
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("klue/roberta-base")
        enc = tok(text, max_length=max_len, padding="max_length",
                  truncation=True, return_tensors="pt")
        return enc["input_ids"].squeeze(0), enc["attention_mask"].squeeze(0)
    except Exception:
        ids  = [ord(c) % 1000 for c in text[:max_len]]
        ids += [0] * (max_len - len(ids))
        mask = [1 if i < len(text) else 0 for i in range(max_len)]
        return (
            torch.tensor(ids, dtype=torch.long),
            torch.tensor(mask, dtype=torch.long),
        )


# ──────────────────────────────────────────────────────────────
# 배치 추론
# ──────────────────────────────────────────────────────────────

def _batch_infer(districts: List[Dict], rainfall_map: Dict[str, float]) -> Dict[str, float]:
    """
    districts × rainfall_map → {id: ml_score}.
    rainfall_map: {district_id: rainfall_1h}
    """
    if _model is None:
        return {}

    sar_list, dem_list, ids_list, mask_list = [], [], [], []

    for d in districts:
        did   = d["id"]
        rain  = rainfall_map.get(did, d.get("rainfall_1h", 10.0))
        r_1h  = d.get("forecast", {}).get("1h", {}).get("rainfall", rain * 1.1)
        r_3h  = d.get("forecast", {}).get("3h", {}).get("rainfall", rain * 1.2)

        sar = _rainfall_to_sar(rain)        # (T, 2, H, W)
        dem = _district_to_dem(d)           # (5, H, W)
        text = _precip_text(d["name"], rain, r_1h, r_3h)
        tok_ids, tok_mask = _tokenize(text)

        sar_list.append(sar)
        dem_list.append(dem)
        ids_list.append(tok_ids)
        mask_list.append(tok_mask)

    try:
        sar_batch  = torch.stack(sar_list)    # (B, T, 2, H, W)
        dem_batch  = torch.stack(dem_list)    # (B, 5, H, W)
        ids_batch  = torch.stack(ids_list)    # (B, L)
        mask_batch = torch.stack(mask_list)   # (B, L)

        with torch.no_grad():
            prob = _model(sar_batch, dem_batch, ids_batch, mask_batch)  # (B, 1, H, W)

        prob_np = prob.squeeze(1).cpu().numpy()   # (B, H, W)
        return {d["id"]: float(prob_np[i].mean()) for i, d in enumerate(districts)}

    except Exception as e:
        logger.warning(f"배치 추론 실패: {e}")
        return {}


# ──────────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────────

def predict_all_horizons(enriched_districts: List[Dict]) -> Dict[str, Dict[str, float]]:
    """
    모든 지구 × {current, 1h, 3h} ML 스코어 반환.

    Returns:
        {district_id: {"current": float, "1h": float, "3h": float}}
    """
    _load_model()
    if _model is None:
        return {}

    # 시나리오별 강수 맵
    current_rain = {d["id"]: d.get("rainfall_1h", 10.0) for d in enriched_districts}
    rain_1h = {
        d["id"]: d.get("forecast", {}).get("1h", {}).get("rainfall", current_rain[d["id"]] * 1.1)
        for d in enriched_districts
    }
    rain_3h = {
        d["id"]: d.get("forecast", {}).get("3h", {}).get("rainfall", current_rain[d["id"]] * 1.2)
        for d in enriched_districts
    }

    ml_current = _batch_infer(enriched_districts, current_rain)
    ml_1h      = _batch_infer(enriched_districts, rain_1h)
    ml_3h      = _batch_infer(enriched_districts, rain_3h)

    result = {}
    for d in enriched_districts:
        did = d["id"]
        result[did] = {
            "current": ml_current.get(did, 0.5),
            "1h":      ml_1h.get(did,      0.5),
            "3h":      ml_3h.get(did,      0.5),
        }

    logger.info(f"ML 추론 완료 — {len(result)}개 지구 × 3 시나리오")
    return result


def blend(rule_score: float, ml_score: float) -> float:
    """rule-based + ML 블렌딩."""
    w_ml   = 0.70 if _model_loaded else 0.35
    w_rule = 1.0 - w_ml
    return round(rule_score * w_rule + ml_score * w_ml, 4)

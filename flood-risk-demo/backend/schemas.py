from pydantic import BaseModel
from typing import Dict


class PredictResponse(BaseModel):
    prob_map: list          # 2-D list [H][W] of float32
    risk_level: str         # "LOW" | "MEDIUM" | "HIGH"
    stats: Dict[str, float] # max_prob, mean_prob, high_risk_pct


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    checkpoint_path: str
    checkpoint_exists: bool

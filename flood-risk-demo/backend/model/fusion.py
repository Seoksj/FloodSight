"""
Fusion modules:
  Stage 1 — CrossAttentionFusion : DEM→SAR cross-attention
  Stage 2 — TextSoftGating       : text-guided soft gating
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class CrossAttentionFusion(nn.Module):
    """
    Stage 1: Z_sar cross-attends to Z_dem.
    Query = Z_sar, Key/Value = Z_dem  (DEM informs SAR representation)

    Input : z_sar (B, N, d), z_dem (B, M, d)
    Output: z_geo (B, N, d)
    """

    def __init__(self, d_model: int = 256, n_heads: int = 8, dropout: float = 0.1):
        super().__init__()
        self.attn = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=n_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.ffn = nn.Sequential(
            nn.Linear(d_model, d_model * 4),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model * 4, d_model),
            nn.Dropout(dropout),
        )

    def forward(self, z_sar: torch.Tensor, z_dem: torch.Tensor) -> torch.Tensor:
        # Cross-attention: SAR queries attend to DEM keys/values
        attn_out, _ = self.attn(
            query=z_sar,
            key=z_dem,
            value=z_dem,
        )
        z = self.norm1(z_sar + attn_out)
        z = self.norm2(z + self.ffn(z))
        return z


class TextSoftGating(nn.Module):
    """
    Stage 2: text soft gating over geo features.

    g = sigmoid(W * [Z_geo_pool ; Z_txt_pool])   (per-token gate vector)
    Z_fused = g * Z_geo + (1 - g) * proj(Z_txt_pool)

    Input : z_geo (B, N, d), z_txt (B, L, d)
    Output: z_fused (B, N, d)
    """

    def __init__(self, d_model: int = 256, dropout: float = 0.1):
        super().__init__()
        self.gate_proj = nn.Linear(d_model * 2, d_model)
        self.txt_proj = nn.Linear(d_model, d_model)
        self.drop = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(d_model)

    def forward(self, z_geo: torch.Tensor, z_txt: torch.Tensor) -> torch.Tensor:
        # Pool text to single vector
        z_txt_pool = z_txt.mean(dim=1, keepdim=True)   # (B, 1, d)
        z_txt_pool = z_txt_pool.expand(-1, z_geo.size(1), -1)  # (B, N, d)

        concat = torch.cat([z_geo, z_txt_pool], dim=-1)  # (B, N, 2d)
        g = torch.sigmoid(self.gate_proj(concat))         # (B, N, d)

        txt_contribution = self.txt_proj(z_txt_pool)      # (B, N, d)
        z_fused = g * z_geo + (1.0 - g) * txt_contribution
        return self.norm(self.drop(z_fused))

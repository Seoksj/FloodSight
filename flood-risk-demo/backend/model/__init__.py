from .encoders import SAREncoder, DEMEncoder, TextEncoder
from .fusion import CrossAttentionFusion, TextSoftGating
from .decoder import UNetDecoder
from .loss import FocalDiceLoss

import torch
import torch.nn as nn


class FloodRiskModel(nn.Module):
    def __init__(
        self,
        d_model: int = 256,
        sar_in_channels: int = 2,
        sar_time_steps: int = 4,
        dem_in_channels: int = 5,
        patch_size: int = 16,
    ):
        super().__init__()
        self.d_model = d_model
        self.patch_size = patch_size

        self.sar_encoder = SAREncoder(
            in_channels=sar_in_channels,
            time_steps=sar_time_steps,
            d_model=d_model,
            patch_size=patch_size,
        )
        self.dem_encoder = DEMEncoder(
            in_channels=dem_in_channels,
            d_model=d_model,
            patch_size=patch_size,
        )
        self.text_encoder = TextEncoder(d_model=d_model)

        self.cross_attn = CrossAttentionFusion(d_model=d_model)
        self.text_gating = TextSoftGating(d_model=d_model)

        self.decoder = UNetDecoder(d_model=d_model, patch_size=patch_size)

    def forward(self, sar, dem, input_ids, attention_mask=None):
        # sar: (B, T, C, H, W), dem: (B, C_dem, H, W)
        B, T, C, H, W = sar.shape

        z_sar, sar_skips = self.sar_encoder(sar)          # (B, N, d), list of skips
        z_dem, dem_skips = self.dem_encoder(dem)          # (B, M, d), list of skips
        z_txt = self.text_encoder(input_ids, attention_mask)  # (B, L, d)

        z_geo = self.cross_attn(z_sar, z_dem)             # (B, N, d)
        z_fused = self.text_gating(z_geo, z_txt)          # (B, N, d)

        prob_map = self.decoder(z_fused, sar_skips, H, W) # (B, 1, H, W)
        return prob_map

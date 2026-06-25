"""
UNetDecoder: token sequence → probability map (B, 1, H, W).
Accepts skip connections from SAR encoder for fine-grained spatial detail.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List


class ConvBnRelu(nn.Sequential):
    def __init__(self, in_ch: int, out_ch: int, kernel_size: int = 3):
        super().__init__(
            nn.Conv2d(in_ch, out_ch, kernel_size, padding=kernel_size // 2, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )


class UpBlock(nn.Module):
    """Upsample × 2, optionally concat skip, then two ConvBnRelu."""

    def __init__(self, in_ch: int, skip_ch: int, out_ch: int):
        super().__init__()
        self.up = nn.Upsample(scale_factor=2, mode="bilinear", align_corners=False)
        self.conv = nn.Sequential(
            ConvBnRelu(in_ch + skip_ch, out_ch),
            ConvBnRelu(out_ch, out_ch),
        )

    def forward(self, x: torch.Tensor, skip: torch.Tensor = None) -> torch.Tensor:
        x = self.up(x)
        if skip is not None:
            # Handle size mismatch from odd resolutions
            if x.shape[-2:] != skip.shape[-2:]:
                x = F.interpolate(x, size=skip.shape[-2:], mode="bilinear", align_corners=False)
            x = torch.cat([x, skip], dim=1)
        return self.conv(x)


class UNetDecoder(nn.Module):
    """
    Input : z_fused (B, N, d_model), skip connections, original (H, W)
    Output: prob_map (B, 1, H, W)

    Upsampling path (patch_size=16 → 4 up-blocks of ×2):
      patch grid → H/8 → H/4 → H/2 → H
    """

    def __init__(self, d_model: int = 256, patch_size: int = 16):
        super().__init__()
        self.d_model = d_model
        self.patch_size = patch_size

        # skip[0]: (B, 32, H, W)   full-res SAR features
        # skip[1]: (B, 64, H/2, W/2) ConvLSTM hidden state
        self.up1 = UpBlock(d_model, 0,  128)          # patch → patch×2
        self.up2 = UpBlock(128,     0,   64)          # → patch×4
        self.up3 = UpBlock(64,      64,  64)          # → H/2, merge skip[1]
        self.up4 = UpBlock(64,      32,  32)          # → H,   merge skip[0]

        self.head = nn.Conv2d(32, 1, kernel_size=1)

    def forward(
        self,
        z_fused: torch.Tensor,
        skips: List[torch.Tensor],
        H: int,
        W: int,
    ) -> torch.Tensor:
        B, N, d = z_fused.shape
        # Reshape token sequence to 2-D feature map
        h_p = H // self.patch_size
        w_p = W // self.patch_size
        x = z_fused.permute(0, 2, 1).reshape(B, d, h_p, w_p)

        x = self.up1(x)                              # (B, 128, h_p*2, w_p*2)
        x = self.up2(x)                              # (B, 64,  h_p*4, w_p*4)
        x = self.up3(x, skips[1] if len(skips) > 1 else None)  # merge ConvLSTM skip
        x = self.up4(x, skips[0] if len(skips) > 0 else None)  # merge SAR skip

        # Ensure output matches original spatial size
        if x.shape[-2:] != (H, W):
            x = F.interpolate(x, size=(H, W), mode="bilinear", align_corners=False)

        return torch.sigmoid(self.head(x))           # (B, 1, H, W)

"""
SAR, DEM, Text encoders for flood risk prediction.

SAR  : (B, T, C, H, W)  → (B, N, d)   ConvLSTM-based temporal encoder
DEM  : (B, C_dem, H, W) → (B, M, d)   ResNet-18 stem
Text : (B, L)            → (B, L, d)   klue/roberta-base (frozen)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Optional, Tuple, List


# ---------------------------------------------------------------------------
# ConvLSTM Cell
# ---------------------------------------------------------------------------

class ConvLSTMCell(nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int, kernel_size: int = 3):
        super().__init__()
        padding = kernel_size // 2
        self.hidden_channels = hidden_channels
        self.gates = nn.Conv2d(
            in_channels + hidden_channels,
            4 * hidden_channels,
            kernel_size,
            padding=padding,
        )

    def forward(
        self,
        x: torch.Tensor,
        h: torch.Tensor,
        c: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        combined = torch.cat([x, h], dim=1)
        gates = self.gates(combined)
        i, f, g, o = gates.chunk(4, dim=1)
        i, f, o = torch.sigmoid(i), torch.sigmoid(f), torch.sigmoid(o)
        g = torch.tanh(g)
        c_next = f * c + i * g
        h_next = o * torch.tanh(c_next)
        return h_next, c_next


# ---------------------------------------------------------------------------
# SAR Encoder (ConvLSTM-based)
# Interface identical so 3D-Swin can be swapped in later.
# ---------------------------------------------------------------------------

class SAREncoder(nn.Module):
    """
    Input : (B, T, C, H, W)
    Output: (B, N, d_model) where N = (H/patch_size) * (W/patch_size)
            + list of skip feature maps for U-Net decoder
    """

    def __init__(
        self,
        in_channels: int = 2,
        time_steps: int = 4,
        d_model: int = 256,
        patch_size: int = 16,
        hidden_channels: int = 64,
    ):
        super().__init__()
        self.patch_size = patch_size
        self.d_model = d_model

        # Per-frame feature extraction (shared weights across time)
        self.frame_enc = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, hidden_channels, 3, stride=2, padding=1),  # H/2
            nn.BatchNorm2d(hidden_channels),
            nn.ReLU(inplace=True),
        )

        # Skip branch: full resolution features (before stride)
        self.skip_enc = nn.Sequential(
            nn.Conv2d(in_channels, 32, 3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )

        self.convlstm = ConvLSTMCell(hidden_channels, hidden_channels)

        # Downsample to patch grid
        total_stride = patch_size // 2  # frame_enc already did /2
        self.patch_proj = nn.Sequential(
            nn.Conv2d(hidden_channels, d_model, kernel_size=total_stride, stride=total_stride),
            nn.Flatten(2),  # (B, d_model, N)
        )

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        B, T, C, H, W = x.shape
        device = x.device

        # Collect skip features from first frame for U-Net
        skip = self.skip_enc(x[:, 0])  # (B, 32, H, W)

        h = torch.zeros(B, 64, H // 2, W // 2, device=device)
        c = torch.zeros_like(h)

        for t in range(T):
            frame = x[:, t]                   # (B, C, H, W)
            feat = self.frame_enc(frame)       # (B, 64, H/2, W/2)
            h, c = self.convlstm(feat, h, c)

        # Project to token sequence
        tokens = self.patch_proj(h)            # (B, d_model, N)
        tokens = tokens.permute(0, 2, 1)       # (B, N, d_model)

        return tokens, [skip, h]


# ---------------------------------------------------------------------------
# DEM Encoder (ResNet-18 stem)
# ---------------------------------------------------------------------------

class ResNetStem(nn.Module):
    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(in_channels, out_channels // 2, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm2d(out_channels // 2),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels // 2, out_channels // 2, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels // 2),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels // 2, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
        )

    def forward(self, x):
        return self.block(x)


class DEMEncoder(nn.Module):
    """
    Input : (B, C_dem, H, W)
    Output: (B, M, d_model) where M = (H/patch_size) * (W/patch_size)
            + list of skip feature maps
    """

    def __init__(
        self,
        in_channels: int = 5,
        d_model: int = 256,
        patch_size: int = 16,
    ):
        super().__init__()
        self.patch_size = patch_size
        stem_ch = 64

        self.stem = ResNetStem(in_channels, stem_ch)    # → H/2

        residual_ch = stem_ch * 2
        self.layer1 = self._make_layer(stem_ch, residual_ch, stride=2)   # → H/4

        total_stride = patch_size // 4
        self.patch_proj = nn.Sequential(
            nn.Conv2d(residual_ch, d_model, kernel_size=total_stride, stride=total_stride),
            nn.Flatten(2),
        )

    def _make_layer(self, in_ch, out_ch, stride):
        return nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, stride=stride, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.ReLU(inplace=True),
        )

    def forward(
        self, x: torch.Tensor
    ) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        s1 = self.stem(x)       # (B, 64, H/2, W/2)
        s2 = self.layer1(s1)    # (B, 128, H/4, W/4)

        tokens = self.patch_proj(s2)            # (B, d_model, M)
        tokens = tokens.permute(0, 2, 1)        # (B, M, d_model)

        return tokens, [s1, s2]


# ---------------------------------------------------------------------------
# Text Encoder (klue/roberta-base, frozen)
# Falls back to a lightweight transformer when transformers is unavailable.
# ---------------------------------------------------------------------------

class _FallbackTextEncoder(nn.Module):
    """Minimal text encoder for environments without huggingface/transformers."""

    def __init__(self, vocab_size: int = 32000, d_model: int = 256, max_len: int = 512):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, d_model, padding_idx=0)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=8, dim_feedforward=512, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        pos = torch.zeros(max_len, d_model)
        positions = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pos[:, 0::2] = torch.sin(positions * div_term)
        pos[:, 1::2] = torch.cos(positions * div_term)
        self.register_buffer("pos_enc", pos.unsqueeze(0))

    def forward(self, input_ids, attention_mask=None):
        x = self.embed(input_ids) + self.pos_enc[:, : input_ids.size(1)]
        key_padding_mask = (attention_mask == 0) if attention_mask is not None else None
        return self.transformer(x, src_key_padding_mask=key_padding_mask)


class TextEncoder(nn.Module):
    """
    Input : input_ids (B, L), attention_mask (B, L) optional
    Output: (B, L, d_model)
    """

    def __init__(self, d_model: int = 256, model_name: str = "klue/roberta-base"):
        super().__init__()
        self.d_model = d_model
        self._use_hf = False

        try:
            from transformers import AutoModel
            self.backbone = AutoModel.from_pretrained(model_name)
            for p in self.backbone.parameters():
                p.requires_grad = False
            hf_hidden = self.backbone.config.hidden_size
            self.proj = nn.Linear(hf_hidden, d_model)
            self._use_hf = True
        except Exception:
            self.backbone = _FallbackTextEncoder(d_model=d_model)
            self.proj = nn.Identity()

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if self._use_hf:
            out = self.backbone(input_ids=input_ids, attention_mask=attention_mask)
            hidden = out.last_hidden_state   # (B, L, hf_hidden)
            return self.proj(hidden)         # (B, L, d_model)
        else:
            return self.backbone(input_ids, attention_mask)  # (B, L, d_model)

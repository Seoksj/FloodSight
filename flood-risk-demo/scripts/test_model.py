"""
스크립트 3: 모델 forward pass shape 검증.
batch_size=1, H=W=256 기준.

Usage (backend 디렉토리에서):
  cd flood-risk-demo/backend
  python ../scripts/test_model.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import torch

B, T, C_sar, H, W = 1, 4, 2, 256, 256
C_dem = 5
L = 64  # text sequence length
d_model = 256

print("=" * 60)
print("FloodRisk 모델 Forward Pass Shape 검증")
print(f"  B={B}, T={T}, H={H}, W={W}, d_model={d_model}")
print("=" * 60)


def test_encoders():
    from model.encoders import SAREncoder, DEMEncoder, TextEncoder

    print("\n[1] SAREncoder")
    sar_enc = SAREncoder(in_channels=C_sar, time_steps=T, d_model=d_model)
    sar = torch.randn(B, T, C_sar, H, W)
    z_sar, sar_skips = sar_enc(sar)
    print(f"  Input : {tuple(sar.shape)}")
    print(f"  Output: {tuple(z_sar.shape)}  (expected: [{B}, N, {d_model}])")
    for i, s in enumerate(sar_skips):
        print(f"  skip[{i}]: {tuple(s.shape)}")
    assert z_sar.shape[0] == B and z_sar.shape[2] == d_model
    print("  [PASS]")

    print("\n[2] DEMEncoder")
    dem_enc = DEMEncoder(in_channels=C_dem, d_model=d_model)
    dem = torch.randn(B, C_dem, H, W)
    z_dem, dem_skips = dem_enc(dem)
    print(f"  Input : {tuple(dem.shape)}")
    print(f"  Output: {tuple(z_dem.shape)}  (expected: [{B}, M, {d_model}])")
    assert z_dem.shape[0] == B and z_dem.shape[2] == d_model
    print("  [PASS]")

    print("\n[3] TextEncoder (fallback)")
    txt_enc = TextEncoder(d_model=d_model)
    ids = torch.randint(0, 1000, (B, L))
    mask = torch.ones(B, L, dtype=torch.long)
    z_txt = txt_enc(ids, mask)
    print(f"  Input : ids={tuple(ids.shape)}")
    print(f"  Output: {tuple(z_txt.shape)}  (expected: [{B}, {L}, {d_model}])")
    assert z_txt.shape == (B, L, d_model)
    print("  [PASS]")

    # Return SAR skips — decoder expects SAR encoder skip channels (32, 64)
    return z_sar, z_dem, z_txt, sar_skips


def test_fusion(z_sar, z_dem, z_txt):
    from model.fusion import CrossAttentionFusion, TextSoftGating
    print("\n[4] CrossAttentionFusion (DEM→SAR)")
    cross = CrossAttentionFusion(d_model=d_model)
    z_geo = cross(z_sar, z_dem)
    print(f"  z_sar : {tuple(z_sar.shape)}")
    print(f"  z_dem : {tuple(z_dem.shape)}")
    print(f"  z_geo : {tuple(z_geo.shape)}")
    assert z_geo.shape == z_sar.shape
    print("  [PASS]")

    print("\n[5] TextSoftGating")
    gating = TextSoftGating(d_model=d_model)
    z_fused = gating(z_geo, z_txt)
    print(f"  z_geo   : {tuple(z_geo.shape)}")
    print(f"  z_txt   : {tuple(z_txt.shape)}")
    print(f"  z_fused : {tuple(z_fused.shape)}")
    assert z_fused.shape == z_sar.shape
    print("  [PASS]")

    return z_fused


def test_decoder(z_fused, skips):
    from model.decoder import UNetDecoder
    print("\n[6] UNetDecoder")
    dec = UNetDecoder(d_model=d_model)
    prob_map = dec(z_fused, skips, H, W)
    print(f"  z_fused  : {tuple(z_fused.shape)}")
    print(f"  prob_map : {tuple(prob_map.shape)}  (expected: [{B}, 1, {H}, {W}])")
    assert prob_map.shape == (B, 1, H, W)
    assert prob_map.min() >= 0.0 and prob_map.max() <= 1.0, "sigmoid 범위 벗어남"
    print("  [PASS]")


def test_full_model():
    from model import FloodRiskModel
    print("\n[7] FloodRiskModel (end-to-end)")
    model = FloodRiskModel(d_model=d_model)
    model.eval()

    sar = torch.randn(B, T, C_sar, H, W)
    dem = torch.randn(B, C_dem, H, W)
    ids = torch.randint(0, 1000, (B, L))
    mask = torch.ones(B, L, dtype=torch.long)

    with torch.no_grad():
        out = model(sar, dem, ids, mask)

    print(f"  SAR input   : {tuple(sar.shape)}")
    print(f"  DEM input   : {tuple(dem.shape)}")
    print(f"  Text input  : {tuple(ids.shape)}")
    print(f"  Output      : {tuple(out.shape)}  (expected: [{B}, 1, {H}, {W}])")
    assert out.shape == (B, 1, H, W)
    print("  [PASS]")


def test_loss():
    from model.loss import FocalDiceLoss
    print("\n[8] FocalDiceLoss")
    loss_fn = FocalDiceLoss()
    pred = torch.rand(B, 1, H, W)
    target = (torch.rand(B, 1, H, W) > 0.5).float()
    loss = loss_fn(pred, target)
    print(f"  pred  : {tuple(pred.shape)}")
    print(f"  target: {tuple(target.shape)}")
    print(f"  loss  : {loss.item():.4f}")
    assert loss.item() > 0
    print("  [PASS]")


if __name__ == "__main__":
    z_sar, z_dem, z_txt, skips = test_encoders()
    z_fused = test_fusion(z_sar, z_dem, z_txt)
    test_decoder(z_fused, skips)
    test_full_model()
    test_loss()
    print("\n" + "=" * 60)
    print("모든 shape 검증 통과!")
    print("=" * 60)

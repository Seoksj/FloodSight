"""
FocalDiceLoss: Focal loss + Dice loss combined.
  alpha=0.25, gamma=2.0, dice_weight=0.5
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    def __init__(self, alpha: float = 0.25, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        # pred: (B, 1, H, W) logits *before* sigmoid  OR probabilities
        # We accept probabilities (after sigmoid); convert to logits for BCE
        bce = F.binary_cross_entropy(pred, target, reduction="none")
        p_t = pred * target + (1 - pred) * (1 - target)
        alpha_t = self.alpha * target + (1 - self.alpha) * (1 - target)
        focal_weight = alpha_t * (1 - p_t) ** self.gamma
        return (focal_weight * bce).mean()


class DiceLoss(nn.Module):
    def __init__(self, smooth: float = 1.0):
        super().__init__()
        self.smooth = smooth

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        pred_flat = pred.reshape(pred.size(0), -1)
        target_flat = target.reshape(target.size(0), -1)
        intersection = (pred_flat * target_flat).sum(dim=1)
        dice = (2 * intersection + self.smooth) / (
            pred_flat.sum(dim=1) + target_flat.sum(dim=1) + self.smooth
        )
        return 1 - dice.mean()


class FocalDiceLoss(nn.Module):
    """
    L = focal_loss + dice_weight * dice_loss

    Inputs:
      pred   : (B, 1, H, W)  — sigmoid probabilities in [0, 1]
      target : (B, 1, H, W)  — binary labels {0, 1}
    """

    def __init__(
        self,
        alpha: float = 0.25,
        gamma: float = 2.0,
        dice_weight: float = 0.5,
    ):
        super().__init__()
        self.focal = FocalLoss(alpha=alpha, gamma=gamma)
        self.dice = DiceLoss()
        self.dice_weight = dice_weight

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        return self.focal(pred, target) + self.dice_weight * self.dice(pred, target)

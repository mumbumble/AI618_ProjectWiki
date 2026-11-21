"""FreqMix: low-frequency amplitude mixing for leaf photos.

Each image is transformed with a 2D FFT per channel and split into amplitude A
and phase P. Inside a centered low-frequency band M, the amplitude of image a is
interpolated with the amplitude of a partner image b from the same episode.
Outside the band the amplitude stays A_a, and the phase P_a is kept unchanged.
The inverse FFT gives the augmented image, which keeps the label of image a.
"""

import torch
import torch.nn as nn


class FreqMix(nn.Module):
    def __init__(self, beta: float = 0.1, lam_low: float = 0.3,
                 lam_high: float = 0.7, p: float = 0.5):
        super().__init__()
        self.beta = beta          # band ratio, share of the shorter side
        self.lam_low = lam_low    # lam ~ Uniform(lam_low, lam_high)
        self.lam_high = lam_high
        self.p = p                # apply probability per image

    def band_mask(self, height: int, width: int, device) -> torch.Tensor:
        # Centered square covering beta * min(H, W) of the shifted spectrum.
        side = max(1, int(round(self.beta * min(height, width))))
        mask = torch.zeros(height, width, device=device)
        top = height // 2 - side // 2
        left = width // 2 - side // 2
        mask[top:top + side, left:left + side] = 1.0
        return mask

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x: (B, C, H, W) images of one episode (support or query set).

        Returns augmented images with the same shape. Labels are unchanged,
        because every output keeps the identity of its own input image a.
        Identity is returned in eval mode.
        """
        if not self.training or x.size(0) < 2:
            return x

        B, C, H, W = x.shape
        device = x.device
        x_f = x.float()

        # Partner b for every image a, drawn from the same episode.
        perm = torch.randperm(B, device=device)
        x_b = x_f[perm]

        # Per-channel 2D FFT with the zero frequency moved to the center.
        F_a = torch.fft.fftshift(torch.fft.fft2(x_f, dim=(-2, -1)), dim=(-2, -1))
        F_b = torch.fft.fftshift(torch.fft.fft2(x_b, dim=(-2, -1)), dim=(-2, -1))
        A_a, P_a = F_a.abs(), F_a.angle()
        A_b = F_b.abs()

        # A_mix = (1 - M) * A_a + M * (lam * A_a + (1 - lam) * A_b)
        lam = torch.empty(B, 1, 1, 1, device=device).uniform_(self.lam_low, self.lam_high)
        M = self.band_mask(H, W, device).view(1, 1, H, W)
        A_mix = (1 - M) * A_a + M * (lam * A_a + (1 - lam) * A_b)

        # Only a random subset of images (probability p) is mixed.
        apply = (torch.rand(B, device=device) < self.p).view(B, 1, 1, 1)
        A_out = torch.where(apply, A_mix, A_a)

        # Keep phase P_a, then inverse FFT back to image space.
        F_out = torch.polar(A_out, P_a)
        F_out = torch.fft.ifftshift(F_out, dim=(-2, -1))
        x_out = torch.fft.ifft2(F_out, dim=(-2, -1)).real

        return x_out.clamp_(0.0, 1.0).to(x.dtype)

"""Audio encoder and expression diffusion model."""
import torch
import torch.nn as nn


class AudioEncoder(nn.Module):
    """Frozen wav2vec 2.0 features projected to the model width."""

    def __init__(self, dim=256):
        super().__init__()
        self.proj = nn.Linear(768, dim)

    def forward(self, feats):
        return self.proj(feats)


class ExpressionDiffusion(nn.Module):
    """Transformer denoiser over FLAME expression coefficients, conditioned on audio and emotion."""

    def __init__(self, n_exp=50, dim=256, n_emotions=8, steps=1000):
        super().__init__()
        self.audio = AudioEncoder(dim)
        self.emotion = nn.Embedding(n_emotions, dim)
        self.inp = nn.Linear(n_exp, dim)
        layer = nn.TransformerEncoderLayer(dim, nhead=4, batch_first=True)
        self.denoiser = nn.TransformerEncoder(layer, num_layers=4)
        self.out = nn.Linear(dim, n_exp)
        self.steps = steps

    def forward(self, noisy_exp, t, audio_feats, emotion):
        h = self.inp(noisy_exp) + self.audio(audio_feats) + self.emotion(emotion)[:, None]
        return self.out(self.denoiser(h))

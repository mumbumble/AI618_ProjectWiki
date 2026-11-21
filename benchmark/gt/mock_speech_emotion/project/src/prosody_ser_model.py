"""ProsodySER: main network for bilingual (Korean-English) speech emotion recognition.

Layout and equations are described in docs/method.md. Forward path:
log-Mel -> Conv Stem -> Transformer Encoder -> Prosody-Aware Pooling -> Emotion Classifier.
Side branch: Prosody Extractor features -> Prosody Encoder -> feeds the pooling.
Second branch: Gradient Reversal -> Language Classifier (ko/en), used only during training.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from prosody_attention import ProsodyAttention


class GradReverse(torch.autograd.Function):
    """Identity in the forward pass, scales gradients by -alpha in the backward pass."""

    @staticmethod
    def forward(ctx, x, alpha):
        ctx.alpha = alpha
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad_output):
        return -ctx.alpha * grad_output, None


def grl_strength(step, steps_per_epoch=325, ramp_epochs=5):
    """DANN-style schedule: reversal strength ramps from 0 to 1 over the first ramp_epochs."""
    p = min(step / float(ramp_epochs * steps_per_epoch), 1.0)
    return 2.0 / (1.0 + math.exp(-10.0 * p)) - 1.0


def conv_out_len(lengths):
    """Frame count after two stride-2 convs (kernel 3, padding 1)."""
    for _ in range(2):
        lengths = torch.div(lengths + 2 - 3, 2, rounding_mode="floor") + 1
    return lengths


class ConvStem(nn.Module):
    def __init__(self, n_mels=80, d_model=256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(n_mels, d_model, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
            nn.Conv1d(d_model, d_model, kernel_size=3, stride=2, padding=1),
            nn.GELU(),
        )

    def forward(self, mel):  # (B, T, n_mels) -> (B, ceil(T/4), d_model)
        return self.net(mel.transpose(1, 2)).transpose(1, 2)


class SinusoidalPositionalEncoding(nn.Module):
    def __init__(self, d_model, dropout, max_len=5000):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(max_len).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe.unsqueeze(0), persistent=False)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        return self.drop(x + self.pe[:, : x.size(1)])


class ProsodyEncoder(nn.Module):
    """Two 1D conv layers (kernel 5, hidden 128, ReLU) plus a projection to out_dim per frame."""

    def __init__(self, prosody_dim=6, hidden=128, out_dim=128, kernel_size=5):
        super().__init__()
        pad = kernel_size // 2
        self.conv1 = nn.Conv1d(prosody_dim, hidden, kernel_size, padding=pad)
        self.conv2 = nn.Conv1d(hidden, hidden, kernel_size, padding=pad)
        self.proj = nn.Conv1d(hidden, out_dim, kernel_size=1)

    def forward(self, prosody, target_len):  # (B, T, 6) -> (B, target_len, out_dim)
        x = F.relu(self.conv1(prosody.transpose(1, 2)))
        x = F.relu(self.conv2(x))
        x = self.proj(x)
        # Bring the 10 ms frame grid onto the 40 ms grid used by the encoder.
        x = F.adaptive_avg_pool1d(x, target_len)
        return x.transpose(1, 2)


class ProsodySER(nn.Module):
    def __init__(self, n_mels=80, d_model=256, num_layers=6, num_heads=4, dropout=0.1,
                 prosody_dim=6, prosody_hidden=128, num_emotions=6, num_langs=2,
                 lambda_init=0.5, pool_heads=4):
        super().__init__()
        self.stem = ConvStem(n_mels, d_model)
        self.pos = SinusoidalPositionalEncoding(d_model, dropout)
        layer = nn.TransformerEncoderLayer(
            d_model, num_heads, dim_feedforward=4 * d_model,
            dropout=dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(layer, num_layers, enable_nested_tensor=False)
        self.prosody_enc = ProsodyEncoder(prosody_dim, prosody_hidden, d_model // 2)
        self.pool = ProsodyAttention(d_model=d_model, prosody_dim=d_model // 2,
                                     num_heads=pool_heads, lambda_init=lambda_init)
        self.emo_head = nn.Sequential(
            nn.LayerNorm(d_model), nn.Dropout(dropout),
            nn.Linear(d_model, d_model), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_model, num_emotions))
        self.lang_head = nn.Sequential(
            nn.Linear(d_model, d_model // 2), nn.GELU(),
            nn.Linear(d_model // 2, num_langs))

    def forward(self, mel, prosody, mel_lens=None, grl_alpha=1.0):
        """mel: (B, T, n_mels) log-Mel; prosody: (B, T, 6) frame-level features on the same hop.
        Returns a dict with 'emotion' and 'language' logits. True in the padding mask = padded frame."""
        h = self.stem(mel)
        T = h.size(1)
        if mel_lens is None:
            mel_lens = torch.full((mel.size(0),), mel.size(1), device=mel.device, dtype=torch.long)
        out_lens = conv_out_len(mel_lens)
        pad_mask = torch.arange(T, device=mel.device)[None, :] >= out_lens[:, None]

        h = self.encoder(self.pos(h), src_key_padding_mask=pad_mask)
        p = self.prosody_enc(prosody, T)
        z = self.pool(h, p, pad_mask)  # (B, d_model) utterance embedding

        emo_logits = self.emo_head(z)
        lang_logits = self.lang_head(GradReverse.apply(z, grl_alpha))
        return {"emotion": emo_logits, "language": lang_logits}


if __name__ == "__main__":
    model = ProsodySER()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"ProsodySER parameters: {n_params / 1e6:.1f}M")
    mel = torch.randn(2, 300, 80)
    pros = torch.randn(2, 300, 6)
    out = model(mel, pros, mel_lens=torch.tensor([300, 240]), grl_alpha=grl_strength(0))
    print({k: tuple(v.shape) for k, v in out.items()})

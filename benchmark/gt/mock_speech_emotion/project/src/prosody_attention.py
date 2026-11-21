"""Prosody-Aware Pooling (PAP) for ProsodySER.

Attention pooling over Transformer frames where the attention logits are
biased by a prosody term computed from the Prosody Encoder outputs p_t.

    e_t = (h_t W_q)(c W_k)^T / sqrt(d_k) + lambda * g_t
    g_t = v^T tanh(W_p p_t)
    a_t = softmax over t (padding masked)
    z   = sum_t a_t h_t
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class ProsodyAttention(nn.Module):
    """Prosody-Aware Pooling with several heads (num_heads=4 by default)."""

    def __init__(self, d_model=256, num_heads=4, prosody_dim=128,
                 prosody_hidden=128, lambda_init=0.5, use_prosody=True):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads
        self.use_prosody = use_prosody

        # Learned query vectors c (one per head) and projections W_q, W_k.
        self.query = nn.Parameter(torch.randn(num_heads, d_model) * 0.02)
        scale = 1.0 / math.sqrt(d_model)
        self.w_q = nn.Parameter(torch.randn(num_heads, d_model, self.d_k) * scale)
        self.w_k = nn.Parameter(torch.randn(num_heads, d_model, self.d_k) * scale)

        if use_prosody:
            # Prosody bias g_t = v^T tanh(W_p p_t), one bias value per head.
            self.w_p = nn.Linear(prosody_dim, prosody_hidden)
            self.v = nn.Linear(prosody_hidden, num_heads, bias=False)
            # Learnable scalar weight of the prosody bias, initialised at 0.5.
            self.lambda_ = nn.Parameter(torch.tensor(float(lambda_init)))

        # Heads are concatenated (num_heads * d_model) and projected to d_model.
        self.out_proj = nn.Linear(num_heads * d_model, d_model)

    def forward(self, h, p=None, mask=None):
        """
        h:    (B, T, d_model)     Transformer encoder frame outputs
        p:    (B, T, prosody_dim) Prosody Encoder outputs p_t
        mask: (B, T) bool, True for valid frames, False for padding
        returns: z (B, d_model) utterance embedding, a (B, T, num_heads) weights
        """
        q = torch.einsum("btd,hdk->bthk", h, self.w_q)           # h_t W_q
        kc = torch.einsum("hd,hdk->hk", self.query, self.w_k)    # c W_k
        e = torch.einsum("bthk,hk->bth", q, kc) / math.sqrt(self.d_k)

        if self.use_prosody:
            if p is None:
                raise ValueError("prosody features p are required when use_prosody=True")
            g = self.v(torch.tanh(self.w_p(p)))                  # (B, T, H)
            e = e + self.lambda_ * g

        if mask is not None:
            e = e.masked_fill(~mask.unsqueeze(-1), float("-inf"))
        a = F.softmax(e, dim=1)                                   # softmax over frames

        heads = torch.einsum("bth,btd->bhd", a, h)                # sum_t a_t h_t per head
        z = self.out_proj(heads.reshape(h.size(0), -1))
        return z, a


if __name__ == "__main__":
    torch.manual_seed(1234)
    pool = ProsodyAttention(d_model=256, num_heads=4, prosody_dim=128,
                            prosody_hidden=128, lambda_init=0.5)
    h = torch.randn(2, 50, 256)
    p = torch.randn(2, 50, 128)
    mask = torch.ones(2, 50, dtype=torch.bool)
    mask[1, 30:] = False                                          # pad second utterance
    z, a = pool(h, p, mask)
    print("z:", tuple(z.shape), "a:", tuple(a.shape), "lambda:", float(pool.lambda_))
    assert torch.allclose(a.sum(dim=1), torch.ones(2, 4), atol=1e-5)
    assert float(a[1, 30:].abs().sum()) == 0.0

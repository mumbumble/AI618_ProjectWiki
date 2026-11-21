"""RepoSum main network.

A Transformer encoder-decoder (6+6 layers, d=512, 8 heads, 32k BPE vocab)
that summarizes a Java function from its body. The k=4 most similar functions
from the same repository ("siblings") are retrieved, encoded with the shared
encoder as "sibling code + sibling summary", and fused into the query states
after the encoder. See docs/method.md for the full description.
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

from sibling_retriever import SiblingRetriever, GatedFusion

PAD_ID, BOS_ID, EOS_ID = 0, 1, 2
RET_WEIGHT = 0.3  # lambda in L = L_ce + lambda * L_ret


class RepoSumModel(nn.Module):
    def __init__(self, vocab_size=32000, d_model=512, n_heads=8, n_layers=6,
                 d_ff=2048, dropout=0.1, k=4, max_pos=512):
        super().__init__()
        self.d_model, self.k = d_model, k
        self.tok = nn.Embedding(vocab_size, d_model, padding_idx=PAD_ID)
        self.pos = nn.Embedding(max_pos, d_model)
        self.drop = nn.Dropout(dropout)
        enc_layer = nn.TransformerEncoderLayer(d_model, n_heads, d_ff, dropout, batch_first=True)
        dec_layer = nn.TransformerDecoderLayer(d_model, n_heads, d_ff, dropout, batch_first=True)
        self.encoder = nn.TransformerEncoder(enc_layer, n_layers)
        self.decoder = nn.TransformerDecoder(dec_layer, n_layers)
        self.retriever = SiblingRetriever(k=k)
        self.fusion = GatedFusion(d_model)
        self.proj = nn.Linear(d_model, vocab_size)

    def _embed(self, ids):
        pos = torch.arange(ids.size(1), device=ids.device).unsqueeze(0)
        return self.drop(self.tok(ids) * math.sqrt(self.d_model) + self.pos(pos))

    @staticmethod
    def pool(states, mask):
        m = mask.unsqueeze(-1).to(states.dtype)
        return (states * m).sum(1) / m.sum(1).clamp(min=1.0)

    def encode(self, ids, mask):
        # mask: True for real tokens, False for padding
        return self.encoder(self._embed(ids), src_key_padding_mask=~mask)

    def embed_code(self, ids, mask):
        """Pooled code embedding e, used by the retriever and by L_ret."""
        return self.pool(self.encode(ids, mask), mask)

    def retrieve(self, e_q, query_id, commit_idx):
        """Top-k siblings from the repo-scoped index (self and later commits excluded)."""
        return self.retriever.search(e_q, query_id=query_id, commit_idx=commit_idx)

    def memory(self, src_ids, src_mask, sib_ids, sib_mask):
        """Query states after the encoder, fused with the sibling context."""
        B, K, L = sib_ids.shape
        h_q = self.encode(src_ids, src_mask)
        e_q = self.pool(h_q, src_mask)
        # siblings go through the shared encoder as "sibling code + sibling summary"
        sm = sib_mask.reshape(B * K, L)
        h_s = self.pool(self.encode(sib_ids.reshape(B * K, L), sm), sm)
        h_s = h_s.view(B, K, self.d_model)
        # h = h_q + g * sum_i(alpha_i * h_i), alpha = softmax(cos / tau), tau = 0.07
        return self.fusion(h_q, e_q, h_s)

    def decode(self, memory, src_mask, tgt_in, tgt_mask):
        T = tgt_in.size(1)
        causal = torch.triu(torch.ones(T, T, dtype=torch.bool, device=tgt_in.device), 1)
        out = self.decoder(self._embed(tgt_in), memory, tgt_mask=causal,
                           tgt_key_padding_mask=~tgt_mask,
                           memory_key_padding_mask=~src_mask)
        return self.proj(out)

    def forward(self, src_ids, src_mask, sib_ids, sib_mask, tgt_in, tgt_mask):
        mem = self.memory(src_ids, src_mask, sib_ids, sib_mask)
        return self.decode(mem, src_mask, tgt_in, tgt_mask)

    @torch.no_grad()
    def greedy_decode(self, src_ids, src_mask, sib_ids, sib_mask, max_len=48):
        """Greedy decoding for quick checks; test-time results use beam size 5."""
        mem = self.memory(src_ids, src_mask, sib_ids, sib_mask)
        ys = torch.full((src_ids.size(0), 1), BOS_ID, dtype=torch.long, device=src_ids.device)
        done = torch.zeros(src_ids.size(0), dtype=torch.bool, device=src_ids.device)
        for _ in range(max_len):
            logits = self.decode(mem, src_mask, ys, torch.ones_like(ys, dtype=torch.bool))
            nxt = logits[:, -1].argmax(-1).masked_fill(done, PAD_ID)
            ys = torch.cat([ys, nxt.unsqueeze(1)], dim=1)
            done |= nxt.eq(EOS_ID)
            if bool(done.all()):
                break
        return ys[:, 1:]


def total_loss(logits, tgt_out, l_ret):
    """L = L_ce + lambda * L_ret; L_ce is token-level cross-entropy of the summary."""
    l_ce = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                           tgt_out.reshape(-1), ignore_index=PAD_ID)
    return l_ce + RET_WEIGHT * l_ret, l_ce

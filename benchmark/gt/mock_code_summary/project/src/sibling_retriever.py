"""Repo-scoped sibling retrieval and gated fusion for RepoSum.

For a query function, retrieve the k most similar functions ("siblings")
from the same repository and fuse their encoded states into the decoder input.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

K_SIBLINGS = 4        # number of siblings kept per query
TAU = 0.07            # temperature for retrieval weights and InfoNCE
LAMBDA_RET = 0.3      # weight of the retrieval loss


class SiblingRetriever:
    """Dense, repo-scoped index of function embeddings."""

    def __init__(self, k=K_SIBLINGS):
        self.k = k
        self.index = {}  # repo_id -> {"ids", "commits", "embs"}

    def build_index(self, repo_id, func_ids, commit_idx, embeddings):
        """Store L2-normalized code embeddings for one repository only."""
        self.index[repo_id] = {
            "ids": list(func_ids),
            "commits": torch.as_tensor(commit_idx),
            "embs": F.normalize(embeddings, dim=-1),
        }

    def retrieve(self, repo_id, query_id, query_commit, query_emb):
        """Return (sibling_ids, top_idx, alpha) for one query function.

        Self-exclusion: the query itself and any function from a commit
        later than the query are removed before scoring (prevents leakage).
        """
        entry = self.index[repo_id]
        q = F.normalize(query_emb, dim=-1)
        cos = entry["embs"] @ q                                   # cos(e_q, e_c)
        not_self = torch.tensor([f != query_id for f in entry["ids"]], dtype=torch.bool)
        valid = (entry["commits"] <= query_commit) & not_self
        cos = cos.masked_fill(~valid, float("-inf"))

        top_cos, top_idx = cos.topk(self.k)
        keep = torch.isfinite(top_cos)                            # repos may be small
        top_cos, top_idx = top_cos[keep], top_idx[keep]
        alpha = torch.softmax(top_cos / TAU, dim=-1)              # alpha_i
        sib_ids = [entry["ids"][i] for i in top_idx.tolist()]
        return sib_ids, top_idx, alpha


class GatedFusion(nn.Module):
    """h = h_q + g * sum_i(alpha_i * h_i),  g = sigmoid(W [h_q ; c])."""

    def __init__(self, d_model=512):
        super().__init__()
        self.gate = nn.Linear(2 * d_model, d_model)               # W

    def forward(self, h_q, h_sib, alpha):
        # h_q: (B, d), h_sib: (B, k, d), alpha: (B, k)
        c = torch.einsum("bk,bkd->bd", alpha, h_sib)              # sibling context c
        g = torch.sigmoid(self.gate(torch.cat([h_q, c], dim=-1)))
        return h_q + g * c


def info_nce(q, pos, neg, tau=TAU):
    """InfoNCE for the retrieval encoder.

    q: (B, d) queries, pos: (B, d) call-graph neighbours of q,
    neg: (B, n, d) other in-batch functions from the same repo.
    All inputs are L2-normalized.
    """
    pos_logit = (q * pos).sum(-1, keepdim=True) / tau
    neg_logit = torch.einsum("bd,bnd->bn", q, neg) / tau
    logits = torch.cat([pos_logit, neg_logit], dim=-1)
    labels = torch.zeros(q.size(0), dtype=torch.long, device=q.device)
    return F.cross_entropy(logits, labels)


def total_loss(l_ce, l_ret, lam=LAMBDA_RET):
    """L = L_ce + lambda * L_ret."""
    return l_ce + lam * l_ret

"""LeafProto network: ResNet-12 encoder, cosine prototype head and the
episodic training loss with the FreqMix consistency term.

The method is described in docs/method.md. Episodes arrive already sampled
and resized to 84x84.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

from freq_mix import FreqMix


class ResBlock(nn.Module):
    """Three 3x3 conv-BN-LeakyReLU layers, 1x1 shortcut, 2x2 max-pool."""

    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.LeakyReLU(0.1),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
            nn.LeakyReLU(0.1),
            nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_ch),
        )
        self.shortcut = nn.Sequential(
            nn.Conv2d(in_ch, out_ch, 1, bias=False),
            nn.BatchNorm2d(out_ch),
        )
        self.act = nn.LeakyReLU(0.1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        return self.pool(self.act(self.body(x) + self.shortcut(x)))


class ResNet12(nn.Module):
    """ResNet-12 with channels 64-160-320-640, returns a 640-d embedding."""

    def __init__(self, channels=(64, 160, 320, 640)):
        super().__init__()
        dims = [3, *channels]
        self.blocks = nn.Sequential(
            *[ResBlock(dims[i], dims[i + 1]) for i in range(len(channels))]
        )
        self.out_dim = channels[-1]

    def forward(self, x):
        x = self.blocks(x)
        return F.adaptive_avg_pool2d(x, 1).flatten(1)


class CosineProtoHead(nn.Module):
    """Cosine logits between query embeddings and class prototypes."""

    def __init__(self, scale_init=10.0):
        super().__init__()
        self.scale = nn.Parameter(torch.tensor(float(scale_init)))

    @staticmethod
    def prototypes(support_emb, support_labels, n_way):
        # p_c = mean of the L2-normalised support embeddings of class c
        emb = F.normalize(support_emb, dim=-1)
        return torch.stack(
            [emb[support_labels == c].mean(dim=0) for c in range(n_way)]
        )

    def forward(self, query_emb, protos):
        q = F.normalize(query_emb, dim=-1)
        p = F.normalize(protos, dim=-1)
        return self.scale.clamp(min=1e-2) * q @ p.t()


class LeafProtoNet(nn.Module):
    def __init__(self, n_way=5, scale_init=10.0, freqmix_beta=0.1, freqmix_p=0.5):
        super().__init__()
        self.n_way = n_way
        self.encoder = ResNet12()
        self.head = CosineProtoHead(scale_init)
        self.freqmix = FreqMix(beta=freqmix_beta, p=freqmix_p)

    def episode_logits(self, support_x, support_y, query_x):
        s_emb = self.encoder(support_x)
        q_emb = self.encoder(query_x)
        protos = self.head.prototypes(s_emb, support_y, self.n_way)
        return self.head(q_emb, protos)

    def forward(self, support_x, support_y, query_x):
        return self.episode_logits(support_x, support_y, query_x)

    def training_loss(self, support_x, support_y, query_x, query_y, lambda_cons=0.5):
        clean_logits = self.episode_logits(support_x, support_y, query_x)
        loss_ce = F.cross_entropy(clean_logits, query_y)

        # FreqMix view: each image is paired with a random partner from the same episode.
        s_perm = torch.randperm(support_x.size(0), device=support_x.device)
        q_perm = torch.randperm(query_x.size(0), device=query_x.device)
        mix_s = self.freqmix(support_x, support_x[s_perm])
        mix_q = self.freqmix(query_x, query_x[q_perm])
        mixed_logits = self.episode_logits(mix_s, support_y, mix_q)

        # Clean view is the detached target of the KL consistency term.
        clean_prob = F.softmax(clean_logits, dim=-1).detach()
        loss_cons = F.kl_div(
            F.log_softmax(mixed_logits, dim=-1), clean_prob, reduction="batchmean"
        )
        loss = loss_ce + lambda_cons * loss_cons
        return loss, loss_ce.detach(), loss_cons.detach()

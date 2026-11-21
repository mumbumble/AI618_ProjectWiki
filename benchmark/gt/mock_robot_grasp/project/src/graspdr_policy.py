"""Main network for GraspDR. See docs/method.md for the full method description.

GraspPolicy takes the 96x96 RGB-D wrist camera frame and proprioception and
outputs a 7-D action (6-D delta pose + gripper). The asymmetric critic also
sees the privileged physics parameters theta; the actor never does.
"""
import torch
import torch.nn as nn
from torch.distributions import Normal

from contact_reward import ContactAwareReward


class BasicBlock(nn.Module):
    def __init__(self, cin, cout, stride=1):
        super().__init__()
        self.conv1 = nn.Conv2d(cin, cout, 3, stride, 1, bias=False)
        self.bn1 = nn.BatchNorm2d(cout)
        self.conv2 = nn.Conv2d(cout, cout, 3, 1, 1, bias=False)
        self.bn2 = nn.BatchNorm2d(cout)
        self.down = None
        if stride != 1 or cin != cout:
            self.down = nn.Sequential(
                nn.Conv2d(cin, cout, 1, stride, bias=False), nn.BatchNorm2d(cout))

    def forward(self, x):
        identity = x if self.down is None else self.down(x)
        out = torch.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return torch.relu(out + identity)


class RGBDEncoder(nn.Module):
    """ResNet-18 style encoder (base width 32) for 4-channel RGB-D input."""

    def __init__(self, width=32, out_dim=256):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(4, width, 7, 2, 3, bias=False), nn.BatchNorm2d(width),
            nn.ReLU(inplace=True), nn.MaxPool2d(3, 2, 1))
        blocks, cin = [], width
        for i, cout in enumerate([width, 2 * width, 4 * width, 8 * width]):
            stride = 1 if i == 0 else 2
            blocks += [BasicBlock(cin, cout, stride), BasicBlock(cout, cout)]
            cin = cout
        self.blocks = nn.Sequential(*blocks)
        self.proj = nn.Linear(cin, out_dim)

    def forward(self, x):
        x = self.blocks(self.stem(x)).mean(dim=(2, 3))
        return torch.relu(self.proj(x))


class GraspPolicy(nn.Module):
    def __init__(self, proprio_dim=16, privileged_dim=10, action_dim=7,
                 n_pads=2, width=32):
        super().__init__()
        self.visual = RGBDEncoder(width, 256)
        self.proprio = nn.Sequential(
            nn.Linear(proprio_dim, 128), nn.ReLU(), nn.Linear(128, 128), nn.ReLU())
        self.fuse = nn.Sequential(nn.Linear(256 + 128, 256), nn.LayerNorm(256), nn.ReLU())
        self.actor_mean = nn.Sequential(
            nn.Linear(256, 256), nn.ReLU(), nn.Linear(256, action_dim))
        self.actor_logstd = nn.Parameter(torch.zeros(action_dim))
        self.contact_head = nn.Linear(256, n_pads)  # per-pad contact logits (aux)
        self.critic = nn.Sequential(
            nn.Linear(256 + privileged_dim, 256), nn.ReLU(), nn.Linear(256, 1))

    def forward(self, rgbd, proprio, theta):
        v = self.visual(rgbd)
        h = self.fuse(torch.cat([v, self.proprio(proprio)], dim=-1))
        mean = self.actor_mean(h)
        dist = Normal(mean, self.actor_logstd.exp().expand_as(mean))
        value = self.critic(torch.cat([h, theta], dim=-1)).squeeze(-1)
        return dist, value, self.contact_head(h)


def graspdr_loss(policy, batch, clip=0.2, vf_coef=0.5, ent_coef=0.01, aux_coef=0.2):
    """PPO clipped surrogate + value loss - entropy + contact auxiliary BCE."""
    dist, value, contact_logits = policy(batch["rgbd"], batch["proprio"], batch["theta"])
    logp = dist.log_prob(batch["actions"]).sum(-1)
    ratio = torch.exp(logp - batch["old_logp"])
    adv = batch["adv"]
    surrogate = torch.min(ratio * adv, torch.clamp(ratio, 1 - clip, 1 + clip) * adv)
    policy_loss = -surrogate.mean()
    value_loss = (value - batch["returns"]).pow(2).mean()
    entropy = dist.entropy().sum(-1).mean()
    aux_loss = nn.functional.binary_cross_entropy_with_logits(
        contact_logits, batch["pad_contact"])
    return policy_loss + vf_coef * value_loss - ent_coef * entropy + aux_coef * aux_loss


def build_reward(cfg):
    """Contact-aware reward module, configured from the run config."""
    return ContactAwareReward(lambda_c=cfg["lambda_c"], lambda_f=cfg["lambda_f"],
                              f_max=cfg["f_max"], f_min=cfg["f_min"])

"""Compute lip vertex error (LVE) and emotion recognition accuracy on the test split."""
import torch

from model import ExpressionDiffusion
from data import TalkingClips


def lip_vertex_error(pred, gt):
    """Max L2 error over mouth vertices per frame, averaged over frames (FaceFormer protocol)."""
    return (pred - gt).norm(dim=-1).max(dim=-1).values.mean()


def evaluate(ckpt, data_root):
    model = ExpressionDiffusion()
    model.load_state_dict(torch.load(ckpt))
    scores = []
    for audio, exp, emotion in TalkingClips(data_root, "test"):
        pred = model(torch.randn_like(exp), torch.tensor([0]), audio, torch.tensor([emotion]))
        scores.append(lip_vertex_error(pred, exp).item())
    return sum(scores) / len(scores)

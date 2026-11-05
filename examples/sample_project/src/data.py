"""Dataset of (audio features, FLAME expression, emotion label) clips."""
from pathlib import Path

import torch
from torch.utils.data import Dataset

EMOTIONS = ["neutral", "happy", "sad", "angry", "fear", "disgust", "surprise", "contempt"]


class TalkingClips(Dataset):
    def __init__(self, root, split="train"):
        self.files = sorted(Path(root, split).glob("*.pt"))

    def __len__(self):
        return len(self.files)

    def __getitem__(self, i):
        clip = torch.load(self.files[i])
        return clip["audio"], clip["exp"], EMOTIONS.index(clip["emotion"])

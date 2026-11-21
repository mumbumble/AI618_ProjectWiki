"""Dataset loading and speaker-independent splits for the KoEn-Emo corpus."""

import logging
import os
import random

import pandas as pd
import soundfile as sf
import torch
from torch.utils.data import DataLoader, Dataset

log = logging.getLogger("prosody_ser.data")

SAMPLE_RATE = 16000
EMOTIONS = ["neutral", "happy", "sad", "angry", "fearful", "surprised"]
EMO2ID = {e: i for i, e in enumerate(EMOTIONS)}
LANG2ID = {"ko": 0, "en": 1}
SPLIT_SIZES = {"train": 10374, "val": 2223, "test": 2223}
SNR_LEVELS = [20, 10, 5, 0]  # babble SNR (dB) for the noise robustness test


def check_speaker_independence(df):
    """Fail loudly if any speaker appears in more than one split."""
    spk = {s: set(df.loc[df["split"] == s, "speaker_id"]) for s in SPLIT_SIZES}
    names = list(spk)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            overlap = spk[a] & spk[b]
            if overlap:
                raise RuntimeError(f"speaker overlap between {a} and {b}: {sorted(overlap)[:5]}")
    return {s: len(v) for s, v in spk.items()}


def mix_babble(wave, babble, snr_db):
    """Add babble noise to a waveform at the requested SNR in dB."""
    babble = babble[: wave.shape[0]]
    p_sig = wave.pow(2).mean().clamp_min(1e-10)
    p_noise = babble.pow(2).mean().clamp_min(1e-10)
    scale = torch.sqrt(p_sig / (p_noise * 10 ** (snr_db / 10)))
    return wave + scale * babble


class KoEnEmoDataset(Dataset):
    def __init__(self, df, root, split, snr_db=None, seed=1234):
        self.meta = df[df["split"] == split].reset_index(drop=True)
        unknown = set(self.meta["emotion"]) - set(EMOTIONS)
        if unknown:
            raise ValueError(f"unknown emotion labels in {split}: {unknown}")
        self.root = root
        self.snr_db = snr_db
        self.rng = random.Random(seed)

    def __len__(self):
        return len(self.meta)

    def _load(self, rel_path):
        wave, sr = sf.read(os.path.join(self.root, rel_path), dtype="float32")
        if sr != SAMPLE_RATE:
            raise ValueError(f"{rel_path}: expected {SAMPLE_RATE} Hz, got {sr}")
        if wave.ndim == 2:
            wave = wave.mean(axis=1)
        return torch.from_numpy(wave)

    def _babble(self, n, k=3):
        # Babble = sum of k other utterances from the same split, cropped to n samples.
        noise = torch.zeros(n)
        for i in self.rng.sample(range(len(self.meta)), k):
            w = self._load(self.meta.iloc[i]["path"])[:n]
            noise[: w.shape[0]] += w
        return noise

    def __getitem__(self, idx):
        row = self.meta.iloc[idx]
        wave = self._load(row["path"])
        if self.snr_db is not None:
            wave = mix_babble(wave, self._babble(wave.shape[0]), self.snr_db)
        return {
            "wave": wave,
            "emotion": EMO2ID[row["emotion"]],
            "lang": LANG2ID[row["lang"]],
            "speaker": row["speaker_id"],
            "utt_id": row["utt_id"],
        }


def collate_batch(batch):
    """Zero-pad waveforms to the longest utterance in the batch (max 7.5 s)."""
    lengths = torch.tensor([b["wave"].shape[0] for b in batch])
    waves = torch.zeros(len(batch), int(lengths.max()))
    for i, b in enumerate(batch):
        waves[i, : b["wave"].shape[0]] = b["wave"]
    return {
        "wave": waves,
        "lengths": lengths,
        "emotion": torch.tensor([b["emotion"] for b in batch]),
        "lang": torch.tensor([b["lang"] for b in batch]),
        "speaker": [b["speaker"] for b in batch],
        "utt_id": [b["utt_id"] for b in batch],
    }


def make_loaders(cfg):
    """Build train/val/test loaders plus one noisy test loader per SNR level."""
    df = pd.read_csv(cfg["metadata_csv"])
    counts = check_speaker_independence(df)
    log.info("speakers per split: %s", counts)

    root, seed, bs = cfg["data_root"], cfg["seed"], cfg["batch_size"]
    workers = cfg.get("num_workers", 4)
    loaders = {}

    for split in ["train", "val", "test"]:
        ds = KoEnEmoDataset(df, root, split, seed=seed)
        if len(ds) != SPLIT_SIZES[split]:
            log.warning("%s has %d utterances, expected %d", split, len(ds), SPLIT_SIZES[split])
        g = torch.Generator().manual_seed(seed)
        loaders[split] = DataLoader(
            ds, batch_size=bs, shuffle=(split == "train"), generator=g,
            num_workers=workers, collate_fn=collate_batch,
        )

    for snr in SNR_LEVELS:
        ds = KoEnEmoDataset(df, root, "test", snr_db=snr, seed=seed)
        loaders[f"test_snr{snr}"] = DataLoader(
            ds, batch_size=bs, shuffle=False, num_workers=workers, collate_fn=collate_batch,
        )
    return loaders

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset


@dataclass
class DatasetMeta:
    label_to_idx: dict[str, int]
    idx_to_label: list[str]
    input_size: int


class SignSequenceDataset(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        samples: list[tuple[Path, int]],
        seq_len: int,
        input_size: int,
    ) -> None:
        self.samples = samples
        self.seq_len = seq_len
        self.input_size = input_size

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        path, label_idx = self.samples[index]
        arr = np.load(path).astype(np.float32)

        if arr.ndim != 2:
            raise ValueError(f"Expected [T, F] in {path}, got {arr.shape}")
        if arr.shape[1] != self.input_size:
            raise ValueError(
                f"Feature size mismatch in {path}: expected {self.input_size}, got {arr.shape[1]}"
            )

        seq = _normalize_length(arr, self.seq_len)
        x = torch.from_numpy(seq)
        y = torch.tensor(label_idx, dtype=torch.long)
        return x, y


def discover_dataset(data_dir: Path) -> tuple[list[tuple[Path, int]], DatasetMeta]:
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    labels = sorted([p.name for p in data_dir.iterdir() if p.is_dir()])
    if not labels:
        raise ValueError(f"No class directories found in {data_dir}")

    label_to_idx = {label: i for i, label in enumerate(labels)}
    samples: list[tuple[Path, int]] = []
    input_size: int | None = None

    for label, idx in label_to_idx.items():
        class_dir = data_dir / label
        files = sorted(class_dir.glob("*.npy"))
        if not files:
            continue
        for path in files:
            arr = np.load(path, mmap_mode="r")
            if arr.ndim != 2:
                raise ValueError(f"Expected [T, F] in {path}, got {arr.shape}")
            if input_size is None:
                input_size = int(arr.shape[1])
            elif int(arr.shape[1]) != input_size:
                raise ValueError(
                    f"Inconsistent feature size in {path}: {arr.shape[1]} != {input_size}"
                )
            samples.append((path, idx))

    if not samples:
        raise ValueError(f"No .npy samples found under {data_dir}")
    if input_size is None:
        raise ValueError("Could not infer input_size")

    meta = DatasetMeta(
        label_to_idx=label_to_idx,
        idx_to_label=[label for label in labels],
        input_size=input_size,
    )
    return samples, meta


def split_samples(
    samples: list[tuple[Path, int]],
    val_ratio: float,
    seed: int,
) -> tuple[list[tuple[Path, int]], list[tuple[Path, int]]]:
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between 0 and 1")

    rng = np.random.default_rng(seed)
    indices = np.arange(len(samples))
    rng.shuffle(indices)

    val_count = max(1, int(len(samples) * val_ratio))
    val_idx = set(indices[:val_count].tolist())

    train_samples = [s for i, s in enumerate(samples) if i not in val_idx]
    val_samples = [s for i, s in enumerate(samples) if i in val_idx]

    if not train_samples or not val_samples:
        raise ValueError("Train/val split failed; need more data")

    return train_samples, val_samples


def _normalize_length(arr: np.ndarray, seq_len: int) -> np.ndarray:
    t, f = arr.shape
    if t == seq_len:
        return arr
    if t > seq_len:
        return arr[-seq_len:, :]

    out = np.zeros((seq_len, f), dtype=np.float32)
    out[:t, :] = arr
    return out

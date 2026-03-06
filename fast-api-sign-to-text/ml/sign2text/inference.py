from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
try:
    import torch
except Exception:  # pragma: no cover
    torch = None

if torch is not None:
    from .model import SignSequenceModel
else:  # pragma: no cover
    SignSequenceModel = None  # type: ignore

VOCAB = ["hallo", "danke", "bitte", "ja", "nein", "ich-verstehe"]


class Predictor(ABC):
    @abstractmethod
    def predict(self, sequence: np.ndarray) -> tuple[str, float, bool]:
        raise NotImplementedError


class StubPredictor(Predictor):
    def __init__(self, input_size: int = 225) -> None:
        self.model = None
        if torch is not None and SignSequenceModel is not None:
            self.model = SignSequenceModel(input_size=input_size, num_classes=len(VOCAB))
            self.model.eval()

    def predict(self, sequence: np.ndarray) -> tuple[str, float, bool]:
        seq = np.asarray(sequence, dtype=np.float32)
        if seq.ndim != 2:
            return "", 0.0, False

        energy = float(np.mean(np.abs(seq)))
        is_final = energy > 0.12

        if torch is not None and self.model is not None:
            with torch.no_grad():
                tensor = torch.from_numpy(seq).unsqueeze(0)
                logits = self.model(tensor)
                probs = torch.softmax(logits, dim=-1).squeeze(0)
                idx = int(torch.argmax(probs).item())
                conf = float(probs[idx].item())
        else:
            idx = int((energy * 1000) % len(VOCAB))
            conf = min(0.95, max(0.2, energy * 2.5))

        text = VOCAB[idx] if energy > 0.02 else ""
        return text, conf, is_final


class TrainedPredictor(Predictor):
    def __init__(self, checkpoint_path: str | None = None) -> None:
        if torch is None or SignSequenceModel is None:
            raise RuntimeError("Torch is not available; cannot use trained provider")
        if not checkpoint_path:
            raise ValueError("checkpoint_path is required for trained provider")

        ckpt_path = Path(checkpoint_path)
        if not ckpt_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {ckpt_path}")

        checkpoint = torch.load(ckpt_path, map_location="cpu")
        input_size = int(checkpoint["input_size"])
        hidden_size = int(checkpoint.get("hidden_size", 128))
        idx_to_label = checkpoint["idx_to_label"]
        num_classes = len(idx_to_label)

        self.model = SignSequenceModel(
            input_size=input_size,
            hidden_size=hidden_size,
            num_classes=num_classes,
        )
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        self.idx_to_label = [str(label) for label in idx_to_label]
        self.seq_len = int(checkpoint.get("seq_len", 32))

    def predict(self, sequence: np.ndarray) -> tuple[str, float, bool]:
        seq = np.asarray(sequence, dtype=np.float32)
        if seq.ndim != 2:
            return "", 0.0, False

        if seq.shape[0] > self.seq_len:
            seq = seq[-self.seq_len :, :]
        elif seq.shape[0] < self.seq_len:
            padded = np.zeros((self.seq_len, seq.shape[1]), dtype=np.float32)
            padded[: seq.shape[0], :] = seq
            seq = padded

        with torch.no_grad():
            tensor = torch.from_numpy(seq).unsqueeze(0)
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=-1).squeeze(0)
            idx = int(torch.argmax(probs).item())
            conf = float(probs[idx].item())

        label = self.idx_to_label[idx]
        is_final = conf >= 0.7
        return label, conf, is_final


def build_predictor(
    provider: str = "stub",
    checkpoint_path: str | None = None,
) -> Predictor:
    if provider == "stub":
        return StubPredictor(input_size=225)
    if provider == "trained":
        return TrainedPredictor(checkpoint_path=checkpoint_path)
    raise ValueError(f"Unknown provider: {provider}")

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = ROOT / "ml"
if str(ML_ROOT) not in sys.path:
    sys.path.append(str(ML_ROOT))

from sign2text.inference import build_predictor  # noqa: E402


class InferenceClient:
    def __init__(self) -> None:
        provider = os.getenv("MODEL_PROVIDER", "stub")
        model_path = os.getenv("MODEL_PATH")
        try:
            self.predictor = build_predictor(
                provider=provider,
                checkpoint_path=model_path,
            )
        except Exception as exc:
            print(f"[inference] provider={provider} failed: {exc}; falling back to stub")
            self.predictor = build_predictor(provider="stub")

    def infer(self, sequence: np.ndarray) -> tuple[str, float, bool]:
        return self.predictor.predict(sequence)

from __future__ import annotations

import torch
from torch import nn


class SignSequenceModel(nn.Module):
    """Einfacher LSTM-Stub fuer Sequenz-zu-Text Klassifikation."""

    def __init__(self, input_size: int, hidden_size: int = 128, num_classes: int = 6):
        super().__init__()
        self.encoder = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=2,
            batch_first=True,
            dropout=0.1,
        )
        self.head = nn.Linear(hidden_size, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.encoder(x)
        pooled = out[:, -1, :]
        return self.head(pooled)

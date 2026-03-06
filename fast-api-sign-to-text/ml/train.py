from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader

from sign2text.dataset import SignSequenceDataset, discover_dataset, split_samples
from sign2text.model import SignSequenceModel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train sign-to-text sequence model")
    parser.add_argument("--data-dir", type=Path, default=Path("data/keypoints"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/sign_model.pt"))
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seq-len", type=int, default=32)
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def evaluate(model: nn.Module, loader: DataLoader, device: torch.device) -> tuple[float, float]:
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total = 0
    criterion = nn.CrossEntropyLoss()

    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            y = y.to(device)
            logits = model(x)
            loss = criterion(logits, y)
            total_loss += float(loss.item()) * x.size(0)
            preds = logits.argmax(dim=1)
            total_correct += int((preds == y).sum().item())
            total += int(x.size(0))

    return total_loss / max(total, 1), total_correct / max(total, 1)


def main() -> None:
    args = parse_args()
    torch.manual_seed(args.seed)

    samples, meta = discover_dataset(args.data_dir)
    train_samples, val_samples = split_samples(samples, args.val_ratio, args.seed)

    train_ds = SignSequenceDataset(
        samples=train_samples,
        seq_len=args.seq_len,
        input_size=meta.input_size,
    )
    val_ds = SignSequenceDataset(
        samples=val_samples,
        seq_len=args.seq_len,
        input_size=meta.input_size,
    )

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = SignSequenceModel(
        input_size=meta.input_size,
        hidden_size=args.hidden_size,
        num_classes=len(meta.idx_to_label),
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    best_val_acc = -1.0
    best_state = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        running_correct = 0
        running_total = 0

        for x, y in train_loader:
            x = x.to(device)
            y = y.to(device)

            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()

            running_loss += float(loss.item()) * x.size(0)
            preds = logits.argmax(dim=1)
            running_correct += int((preds == y).sum().item())
            running_total += int(x.size(0))

        train_loss = running_loss / max(running_total, 1)
        train_acc = running_correct / max(running_total, 1)
        val_loss, val_acc = evaluate(model, val_loader, device)

        print(
            f"epoch={epoch} train_loss={train_loss:.4f} train_acc={train_acc:.4f} "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {
                "model_state_dict": model.state_dict(),
                "label_to_idx": meta.label_to_idx,
                "idx_to_label": meta.idx_to_label,
                "input_size": meta.input_size,
                "seq_len": args.seq_len,
                "hidden_size": args.hidden_size,
            }

    if best_state is None:
        raise RuntimeError("Training did not produce a checkpoint")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(best_state, args.output)

    metrics_path = args.output.with_suffix(".metrics.json")
    metrics_path.write_text(
        json.dumps({"best_val_acc": best_val_acc, "samples": len(samples)}, indent=2),
        encoding="utf-8",
    )

    print(f"Saved checkpoint: {args.output}")
    print(f"Saved metrics: {metrics_path}")


if __name__ == "__main__":
    main()

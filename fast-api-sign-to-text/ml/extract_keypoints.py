from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from backend.app.keypoints import FEATURE_SIZE, KeypointExtractor  # noqa: E402

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract MediaPipe keypoints from videos")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/raw"),
        help="Input dir with class folders containing videos",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/keypoints"),
        help="Output dir for .npy sequence files",
    )
    parser.add_argument(
        "--frame-step",
        type=int,
        default=1,
        help="Use every Nth frame (1 = all)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=0,
        help="Optional hard cap per video (0 = no cap)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )
    return parser.parse_args()


def iter_videos(path: Path) -> list[Path]:
    return sorted(
        [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS]
    )


def read_video_keypoints(
    video_path: Path,
    extractor: KeypointExtractor,
    frame_step: int,
    max_frames: int,
) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    vectors: list[np.ndarray] = []
    frame_idx = 0
    used = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        if frame_idx % frame_step == 0:
            vec = extractor.extract(frame).vector
            if vec.shape[0] != FEATURE_SIZE:
                raise RuntimeError(
                    f"Unexpected feature size {vec.shape[0]} in {video_path}, expected {FEATURE_SIZE}"
                )
            vectors.append(vec)
            used += 1
            if max_frames > 0 and used >= max_frames:
                break

        frame_idx += 1

    cap.release()

    if not vectors:
        raise RuntimeError(f"No frames extracted from {video_path}")

    return np.stack(vectors, axis=0).astype(np.float32)


def main() -> None:
    args = parse_args()
    if args.frame_step < 1:
        raise ValueError("--frame-step must be >= 1")

    input_dir = args.input_dir if args.input_dir.is_absolute() else Path.cwd() / args.input_dir
    output_dir = args.output_dir if args.output_dir.is_absolute() else Path.cwd() / args.output_dir

    if not input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")

    extractor = KeypointExtractor()
    if not extractor.enabled:
        raise RuntimeError(
            "MediaPipe keypoint extraction is unavailable in this Python env. "
            "Use Python 3.11/3.12 and reinstall mediapipe."
        )

    videos = iter_videos(input_dir)
    if not videos:
        raise ValueError(f"No video files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(videos)
    success = 0
    failed = 0
    manifest: list[dict[str, object]] = []

    for idx, video_path in enumerate(videos, start=1):
        rel = video_path.relative_to(input_dir)
        label = rel.parts[0] if len(rel.parts) > 1 else "unknown"

        out_dir = output_dir / label
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{video_path.stem}.npy"

        print(f"[{idx}/{total}] {video_path}")

        if out_path.exists() and not args.overwrite:
            print(f"  skip (exists): {out_path}")
            manifest.append(
                {
                    "video": str(video_path),
                    "label": label,
                    "output": str(out_path),
                    "status": "skipped_exists",
                }
            )
            continue

        try:
            seq = read_video_keypoints(
                video_path=video_path,
                extractor=extractor,
                frame_step=args.frame_step,
                max_frames=args.max_frames,
            )
            np.save(out_path, seq)
            success += 1
            manifest.append(
                {
                    "video": str(video_path),
                    "label": label,
                    "output": str(out_path),
                    "status": "ok",
                    "shape": list(seq.shape),
                }
            )
            print(f"  saved: {out_path} shape={seq.shape}")
        except Exception as exc:
            failed += 1
            manifest.append(
                {
                    "video": str(video_path),
                    "label": label,
                    "output": str(out_path),
                    "status": "error",
                    "error": str(exc),
                }
            )
            print(f"  error: {exc}")

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("---")
    print(f"videos={total} success={success} failed={failed}")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()

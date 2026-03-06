from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None


POSE_LANDMARKS = 33
HAND_LANDMARKS = 21
XYZ = 3
FEATURE_SIZE = (POSE_LANDMARKS + HAND_LANDMARKS * 2) * XYZ


@dataclass
class ExtractionResult:
    vector: np.ndarray


class KeypointExtractor:
    def __init__(self) -> None:
        self.enabled = mp is not None and hasattr(mp, "solutions")
        if not self.enabled:
            self.pose = None
            self.hands = None
            return

        try:
            self.pose = mp.solutions.pose.Pose(
                static_image_mode=False,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
                model_complexity=1,
            )
            self.hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
        except Exception:
            self.enabled = False
            self.pose = None
            self.hands = None

    def extract(self, frame_bgr: np.ndarray) -> ExtractionResult:
        if not self.enabled:
            return ExtractionResult(vector=np.zeros(FEATURE_SIZE, dtype=np.float32))

        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

        pose_result = self.pose.process(frame_rgb)
        hands_result = self.hands.process(frame_rgb)

        pose_vec = np.zeros((POSE_LANDMARKS, XYZ), dtype=np.float32)
        if pose_result.pose_landmarks:
            for i, lm in enumerate(pose_result.pose_landmarks.landmark[:POSE_LANDMARKS]):
                pose_vec[i] = [lm.x, lm.y, lm.z]

        left_vec = np.zeros((HAND_LANDMARKS, XYZ), dtype=np.float32)
        right_vec = np.zeros((HAND_LANDMARKS, XYZ), dtype=np.float32)
        if hands_result.multi_hand_landmarks and hands_result.multi_handedness:
            for hand_lm, handedness in zip(
                hands_result.multi_hand_landmarks,
                hands_result.multi_handedness,
            ):
                label = handedness.classification[0].label.lower()
                target = left_vec if label == "left" else right_vec
                for i, lm in enumerate(hand_lm.landmark[:HAND_LANDMARKS]):
                    target[i] = [lm.x, lm.y, lm.z]

        combined = np.concatenate(
            [pose_vec.flatten(), left_vec.flatten(), right_vec.flatten()]
        ).astype(np.float32)
        return ExtractionResult(vector=combined)

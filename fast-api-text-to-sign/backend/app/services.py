from datetime import datetime, timezone

from app.sign_repr import NonManualFeature, SignRepresentation, SignToken


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_gloss(text: str) -> str:
    # Placeholder rule-based conversion. Replace with ML/engine integration.
    words = [w.strip(".,!?;:") for w in text.upper().split()]
    words = [w for w in words if w]
    return " ".join(words)


def translate_text_to_sign_repr(text: str) -> SignRepresentation:
    # Demo representation. Replace with real NLP + sign-linguistic model.
    gloss = to_gloss(text)
    parts = gloss.split()

    tokens: list[SignToken] = []
    time_cursor = 0
    step_ms = 420

    for part in parts:
        start = time_cursor
        end = start + step_ms
        tokens.append(SignToken(gloss=part, start_ms=start, end_ms=end))
        time_cursor = end

    non_manual: list[NonManualFeature] = []
    if tokens:
        non_manual.append(
            NonManualFeature(
                kind="eyebrow",
                value="neutral",
                start_ms=tokens[0].start_ms,
                end_ms=tokens[-1].end_ms,
            )
        )

    return SignRepresentation(
        language="dgs",
        gloss=gloss,
        tokens=tokens,
        non_manual=non_manual,
        meta={"generator": "demo-rule-based-v1"},
    )

"""Fast text and stream character encoding detection using Rust chardetng."""
from __future__ import annotations

try:
    import chardetng_py
except ImportError:  # pragma: no cover
    chardetng_py = None  # type: ignore[assignment]

__all__ = ["detect_encoding"]


def detect_encoding(data: bytes, fallback: str = "utf-8") -> str:
    """Detect the character encoding of bytes using Rust chardetng, falling back safely."""
    if not data:
        return fallback
    if chardetng_py is not None:
        try:
            detected = chardetng_py.detect(data)
            if detected:
                return str(detected).lower()
        except Exception:  # pragma: no cover
            pass
    return fallback

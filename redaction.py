"""Bounded-buffer streaming redaction for common PII patterns."""
import re

EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]{1,64}@[A-Z0-9.-]{1,190}\.[A-Z]{2,24}\b")
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CARD = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
PATTERNS = (EMAIL, SSN, CARD)


def redact_complete_text(text: str) -> str:
    for pattern in PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


class StreamingRedactor:
    """Retain a rolling tail and move the emission boundary left if a PII match crosses it."""
    def __init__(self, overlap: int = 320):
        if overlap < 320:
            raise ValueError("overlap must be at least 320 characters for configured email patterns")
        self.overlap = overlap
        self.buffer = ""

    def push(self, chunk: str) -> str:
        self.buffer += chunk
        if len(self.buffer) <= self.overlap:
            return ""

        boundary = len(self.buffer) - self.overlap
        # Never split a detected sensitive value across emitted and retained portions.
        for pattern in PATTERNS:
            for match in pattern.finditer(self.buffer):
                if match.start() < boundary < match.end():
                    boundary = min(boundary, match.start())

        safe = self.buffer[:boundary]
        self.buffer = self.buffer[boundary:]
        return redact_complete_text(safe)

    def finish(self) -> str:
        tail, self.buffer = self.buffer, ""
        return redact_complete_text(tail)

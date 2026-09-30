"""Shared data structures used across the app."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SourceDocument:
    """A user-provided file (or image) that holds the data to fill forms with."""

    path: str
    name: str
    kind: str  # "text" | "image"
    text: str = ""          # extracted text content (for text-like sources)
    image_b64: str = ""     # base64 payload (for image sources)
    media_type: str = ""    # e.g. "image/png" (for image sources)

    def label(self) -> str:
        return self.name


@dataclass
class FieldFill:
    """A single detected field on screen plus the value the AI proposes for it."""

    label: str
    value: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 1.0
    enabled: bool = True

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class CaptureRegion:
    """A screen region in absolute (virtual desktop) pixel coordinates."""

    x: int
    y: int
    width: int
    height: int

    def to_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


@dataclass
class FillPlan:
    """Result of AI analysis: the fields found plus the values proposed for them."""

    region: CaptureRegion
    fields: list[FieldFill] = field(default_factory=list)
    notes: str = ""

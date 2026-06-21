"""Shared domain enumerations."""

from enum import Enum


class MemoryType(Enum):
    """Supported cognitive memory categories."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    WORKING = "working"
    REFLECTION = "reflection"


class Emotion(Enum):
    """Basic emotion labels extracted from conversation content."""

    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    WORRIED = "worried"
    NEUTRAL = "neutral"

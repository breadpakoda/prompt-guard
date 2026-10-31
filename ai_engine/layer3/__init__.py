"""
Layer 3 – Contextual Prompt Injection Detection

Exports:
    is_danger_l3(conversation: list[dict]) -> bool
"""

from .detector import is_danger_l3

__all__ = ["is_danger_l3"]


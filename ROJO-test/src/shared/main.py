"""Shared utility module."""


def clamp(value, min_val, max_val):
    """Clamp value between min and max."""
    if value < min_val:
        return min_val
    if value > max_val:
        return max_val
    return value

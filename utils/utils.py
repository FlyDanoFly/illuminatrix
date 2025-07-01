from math import fmod
from typing import Any, Sequence

from constants.constants import ColorType


def cycle(cycle_source: Sequence[Any]):
    if len(cycle_source) < 2:
        raise ValueError("Need at least two elements to cycle through")
    idx = 0
    while True:
        yield cycle_source[idx]
        idx += 1
        if idx >= len(cycle_source):
            idx = 0


def is_normalized(f: float) -> bool:
    return 0.0 <= f <= 1.0


def hsv_to_rgb(hue: float, sat: float, val:float) -> ColorType:
    """Convert normalized hue, saturation, and value to their red, green, blue representation"""
    if not all(map(is_normalized, (hue, sat, val))):
        raise ValueError("all hsv values need to be between [0.0-1.0] h,s,v=", hue, sat, val)

    chroma = sat * val
    x = chroma * (1.0 - abs(fmod(hue * 6, 2) - 1.0))
    step = 1.0/6.0
    if 0 <= hue < step:
        r1 = chroma
        g1 = x
        b1 = 0
    elif 1.0 * step <= hue < 2.0 * step:
        r1 = x
        g1 = chroma
        b1 = 0
    elif 2.0 * step <= hue < 3.0 * step:
        r1 = 0
        g1 = chroma
        b1 = x
    elif 3.0 * step <= hue < 4.0 * step:
        r1 = 0
        g1 = x
        b1 = chroma
    elif 4.0 * step <= hue < 5.0 * step:
        r1 = x
        g1 = 0
        b1 = chroma
    elif 5.0 * step <= hue < 6.0 * step:
        r1 = chroma
        g1 = 0
        b1 = x
    else:
        raise ValueError(f"out of range hue={hue}")
    r = r1 + (val - chroma)
    g = g1 + (val - chroma)
    b = b1 + (val - chroma)
    return r, g, b

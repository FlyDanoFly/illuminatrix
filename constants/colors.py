from typing import Final

from constants.constants import ColorType

WHITE: Final[ColorType] = (1.0, 1.0, 1.0)
BLACK: Final[ColorType] = (0.0, 0.0, 0.0)
RED: Final[ColorType] = (1.0, 0.0, 0.0)
YELLOW: Final[ColorType] = (1.0, 1.0, 0.0)
GREEN: Final[ColorType] = (0.0, 1.0, 0.0)
AQUA: Final[ColorType] = (0.0, 1.0, 1.0)
BLUE: Final[ColorType] = (0.0, 0.0, 1.0)
PURPLE: Final[ColorType] = (1.0, 0.0, 1.0)

PRIMARY_COLORS: Final[tuple[ColorType, ...]] = (
    RED,
    YELLOW,
    GREEN,
    AQUA,
    BLUE,
    PURPLE,
)

RAINBOW: Final[tuple[ColorType, ...]] = (
    (1.0, 0.0, 0.0),
    (0.85, .42, 0),
    (1.0, 1.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.53, 0.11, 0.8),
    (0.85, 0.3, 0.68)
)
# DULL_RAINBOW = [(0.49, 0.16, 0.16), (0.63, .37, 0.13), (0.75, 0.67, 0.08), (0.37, 0.53, 0.29), (0.25, 0.36, 0.53), (0.37, 0.06, 0.47), (0.15, 0.04, 0.38)]

DULL_RAINBOW: Final[tuple[ColorType, ...]] = (
    (.1, 0.0, 0.0),
    (0.085, .042, 0.0),
    (0.1, 0.1, 0.0),
    (0.0, 0.1, 0.0),
    (0.0, 0.0, 0.1),
    (0.053, 0.011, 0.08),
    (0.085, 0.03, 0.068)
)

# TODO: From Lucy's sim
# COLOR_DICTIONARY = dict(zip(list(TowerLight), RAINBOW))
# DULL_COLOR_DICTIONARY = dict(zip(list(TowerLight), DULL_RAINBOW))

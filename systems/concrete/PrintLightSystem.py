import time

from bases.LightSystem import LightSystem
from constants.constants import ColorType, LightPos, TowerEnum

# A fade effect changes colors every frame; per tower, print the latest
# color at most this often so the stream stays readable
PRINT_INTERVAL_SECS = 0.5


class PrintLightSystem(LightSystem):
    """Prints tower color changes; the console is the light.

    Change-driven and throttled: set() only stages, render() prints a
    tower when its color differs from the last printed one and the
    per-tower interval has passed — so a fade shows a few samples and
    always settles on its final color.
    """

    def __init__(self, **_):
        self._current: dict[TowerEnum, tuple[ColorType, LightPos]] = {}
        self._printed: dict[TowerEnum, tuple[ColorType, LightPos]] = {}
        self._last_print_secs: dict[TowerEnum, float] = {}

    def _set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        self._current[tower_enum] = (color, light_pos)

    def update(self, delta_secs: float) -> None:
        pass

    def render(self) -> None:
        now = time.monotonic()
        for tower_enum, (color, light_pos) in self._current.items():
            if self._printed.get(tower_enum) == (color, light_pos):
                continue
            if now - self._last_print_secs.get(tower_enum, float("-inf")) < PRINT_INTERVAL_SECS:
                continue
            self._printed[tower_enum] = (color, light_pos)
            self._last_print_secs[tower_enum] = now
            pos = "" if light_pos == LightPos.All else f" [{light_pos}]"
            print(f"Lights: {tower_enum.name} -> ({color[0]:.2f}, {color[1]:.2f}, {color[2]:.2f}){pos}")

    def startup(self) -> None:
        print("PrintLightSystem: startup")

    def shutdown(self) -> None:
        print("PrintLightSystem: shutdown")

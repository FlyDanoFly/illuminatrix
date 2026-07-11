from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import ColorType, LightPos, TowerEnum


class LightSystem(BaseSystem):
    # Class-level default so subclasses that skip super().__init__()
    # still read 1.0 (full brightness) until someone sets it
    _master_brightness: float = 1.0

    def set_master_brightness(self, brightness: float) -> None:
        """Scale every subsequent color by 0.0-1.0 before it reaches the
        hardware. Colors already showing keep their old scale until the
        next set() for that tower — the ambient game and effects rewrite
        theirs every frame, so in practice the change lands immediately."""
        self._master_brightness = brightness

    def set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        """Set one tower's lights to an (r, g, b) of 0.0-1.0 floats,
        scaled by the master brightness on its way to _set()."""
        brightness = self._master_brightness
        if brightness != 1.0:
            color = (color[0] * brightness, color[1] * brightness, color[2] * brightness)
        self._set(tower_enum, color, light_pos)

    @abstractmethod
    def _set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        """Deliver the already-brightness-scaled color to the output."""

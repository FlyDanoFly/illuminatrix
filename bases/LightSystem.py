from abc import abstractmethod

from bases.BaseSystem import BaseSystem
from constants.constants import ColorType, LightPos, TowerEnum


class LightSystem(BaseSystem):
    @abstractmethod
    def set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        pass

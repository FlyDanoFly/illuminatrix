from BaseSystem import BaseSystem
from constants import ColorType, LightPos, SystemIdentifier


class LightSystem(BaseSystem):
    num_towers: int
    towers: list[ColorType]

    def setup(self, num_towers: int):
        self.num_towers = num_towers
        black: ColorType = (0.0, 0.0, 0.0,)
        self.towers =  list((black,)*self.num_towers)

    def set(self, system_id: SystemIdentifier, color: ColorType, light: LightPos=LightPos.All):
        self.towers[system_id] = color

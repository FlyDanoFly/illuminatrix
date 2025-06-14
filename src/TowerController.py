from Tower import Tower
from constants import ColorType, LightPos, TowerEnum


class TowerController:
    def __init__(self, towers: list[Tower], one_indexed: bool = True):
        self._towers = towers
        self._one_indexed = one_indexed

    def __getitem__(self, index):
        if isinstance(index, TowerEnum):
            index = index.value - 1
        elif self._one_indexed:
            index -= 1
        return self._towers[index]

    def set_color(self, color: ColorType, light: LightPos = LightPos.All):
        for tower in self._towers:
            tower.set_color(color, light)

    def play_sounds(self, sound):
        for tower in self._towers:
            tower.play_sound(sound)

from constants import ColorType, LightPos, TowerEnum
from Tower import Tower


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

    def __iter__(self):
        return iter(self._towers)

    def set_color(self, color: ColorType, light: LightPos = LightPos.All):
        for tower in self._towers:
            tower.set_color(color, light)

    def play_sound(self, sound):
        # TODO: change to a log
        print(f"Playing sound: {sound}")
        # TODO: Tower controller should probably have a sound system? This is a temporary solution to play sound on all the towers using the first tower
        # TODO: alternatively I can call the play_sound method on each tower, it's not a big deal really, but there may be coordination issues if the sound system is not shared
        self._towers[0].sound_system.play(sound)
        # for tower in self._towers:
        #     tower.play_sound(sound)

    def are_any_sounds_playing(self) -> bool:
        return self._towers[0].sound_system.are_any_sounds_playing()

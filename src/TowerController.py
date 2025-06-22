import logging

from constants import ColorType, LightPos
from Tower import Tower

logger = logging.getLogger(__name__)


class TowerController:
    def __init__(self, towers: list[Tower], one_indexed: bool = True):
        # TODO: generate the towers in here rather than having them passed, pass the systems instead
        """Init the controller for the towers.

        Args:
            towers - a list of the towers in Illuminatrix
            one_indexed - TowerController can be indexed by TowerController[TowerEnum] or by integers TowerController[0-indexed] or TowerController[1-indexed], note the one-indexed only applies to referencing them by ints
        """
        self._towers = towers
        self._one_indexed = one_indexed

    def __getitem__(self, index):
        # TODO: I'm having trouble with isinstance(TowerEnum), doing a workaround until I figure out why
        # if isinstance(index, TowerEnum):
        #     # Convert the enmu to a value to index into the array
        #     index = index.value - 1
        # elif self._one_indexed:
        #     index -= 1
        # return self._towers[index]
        # print("1-->", id(index))
        # print("1-->", id(index.__class__))
        # print("1-->", id(TowerEnum))
        # for tower in TowerEnum:
        #     print("2-->", id(tower))
        # print("3-->", isinstance(index, TowerEnum))
        # print("3-->", isinstance(index.__class__, TowerEnum))
        # For the time being, act as if it is a TowerEnum then assume it's an int.
        try:
            index = index.value - 1
        except AttributeError:
            if self._one_indexed:
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
        self._towers[0]._sound_system.play(sound)
        # for tower in self._towers:
        #     tower.play_sound(sound)

    def are_any_sounds_playing(self) -> bool:
        return self._towers[0]._sound_system.are_any_sounds_playing()

    def any_switch_pressed(self) -> bool:
        return any(tower.get_switch_state() for tower in self._towers)

import logging

from constants import ColorType, LightPos, TowerEnum, tower_to_system_identifier
from SystemFactory import SystemFactory
from Tower import Tower

logger = logging.getLogger(__name__)


class TowerController:
    def __init__(self, system_factory: SystemFactory, one_indexed: bool = True):
        # TODO: generate the towers in here rather than having them passed, pass the systems instead
        """Init the controller for the towers.

        Args:
            towers - a list of the towers in Illuminatrix
            one_indexed - TowerController can be indexed by TowerController[TowerEnum] or by integers TowerController[0-indexed] or TowerController[1-indexed], note the one-indexed only applies to referencing them by ints
        """
        self._light_system = system_factory.get_light_system()
        self._sound_system = system_factory.get_sound_system()
        self._input_system = system_factory.get_input_system()
        towers = [
            Tower(
                tower_enum,
                tower_to_system_identifier[tower_enum],
                self._light_system,
                self._sound_system,
                self._input_system,
            )
            for tower_enum in TowerEnum
        ]
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
        self._sound_system.play(sound)

    def are_any_sounds_playing(self) -> bool:
        return self._sound_system.are_any_sounds_playing()

    def any_switch_pressed(self) -> bool:
        return any(tower.get_switch_state() for tower in self._towers)

import logging
from typing import Generator, Iterator

from bases.BaseEffect import BaseEffect
from constants.constants import (
    ColorType,
    LightPos,
    TowerEnum,
)
from managers.ManagerSingletonFactory import ManagerSingletonFactory
from systems.SystemSingletonFactory import SystemSingletonFactory

from .Tower import Tower

logger = logging.getLogger(__name__)


class TowerController:
    def __init__(self, system: SystemSingletonFactory, manager: ManagerSingletonFactory, one_indexed: bool = True):
        """Init the controller for the towers.

        Args:
            towers - a list of the towers in Illuminatrix
            one_indexed - if True, using `lookup()` will be 1-indexed (1-8), otherwise it will be 0-indexed (0-7)
        """
        self._light_system = system.get_light_system()
        self._sound_system = system.get_sound_system()
        self._input_system = system.get_input_system()
        self._effects = manager.get_effect_manager()
        self._towers: dict[TowerEnum, Tower]
        self._towers = {
            tower_enum: Tower(
                tower_enum,
                system,
                manager,
            )
            for tower_enum in TowerEnum
        }
        self._one_indexed = one_indexed

    def lookup(self, index: int) -> Tower:
        """Lookup a tower by its index, either 0-indexed or 1-indexed.

        Args:
            tower - the index of the tower, either 0-indexed or 1-indexed based on the _one_indexed flag

        Returns:
            The Tower object at the specified index.
        """
        if not self._one_indexed:
            index += 1
        key = TowerEnum(index)
        return self._towers[key]

    def __getitem__(self, key: TowerEnum) -> Tower:
        return self._towers[key]

    def __iter__(self) -> Iterator[TowerEnum]:
        return iter(self._towers)

    def keys(self) -> Iterator[TowerEnum]:
        """Yield each tower's enum."""
        return iter(self._towers)

    def values(self) -> Iterator[Tower]:
        """Yield each Tower object."""
        return iter(self._towers.values())

    def items(self) -> Generator[tuple[TowerEnum, Tower]]:
        """Yield each tower's enum and the corresponding Tower object."""
        for tower_enum, tower in self._towers.items():
            yield tower_enum, tower

    def set_color(self, color: ColorType, light: LightPos = LightPos.All):
        for tower in self._towers.values():
            tower.set_color(color, light)

    def load_sound_bank(self, sound_bank: str):
        """Load a sound bank for the sound system."""
        self._sound_system.load_sound_bank(sound_bank)

    def play_sound(self, sound, volume: float = 1.0, num_loops: int = 0) -> None:
        # TODO: change to a log
        print(f"Playing sound: {sound}")
        self._sound_system.play(sound, volume=volume, num_loops=num_loops)

    def fade_out(self, fade_secs: float = 0.25):
        """Fade out all sounds."""
        self._sound_system.stop_all(fade_secs)

    def are_any_sounds_playing(self) -> bool:
        return self._sound_system.are_any_sounds_playing()

    def any_switch_pressed(self) -> bool:
        return any(tower.is_switch_pressed() for tower in self._towers.values())

    def start_effect(self, effect: BaseEffect):
        self._effects.start_effect(effect)

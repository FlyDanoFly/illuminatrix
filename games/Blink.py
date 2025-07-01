from bases import BaseGame
from components.TowerController import TowerController
from constants.colors import BLACK, DULL_RAINBOW, RAINBOW
from effects.BlinkEffect import BlinkEffect


class Blink(BaseGame):
    def __init__(self, tower_controller: TowerController):
        self._towers = tower_controller
        self._effects = [
            BlinkEffect(
                [tower_enum],
                low_color=DULL_RAINBOW[tower_enum.value - 1],
                high_color=RAINBOW[tower_enum.value - 1],
                low_time_sec=0.25,
                high_time_sec=0.5,
                num_loops=0,
            ) for tower_enum in tower_controller
        ]
        for effect in self._effects:
            self._towers.start_effect(effect)

    def first_frame_update(self) -> None:
        """Override this to set up a first frame before updating"""
        self._towers.set_color(BLACK)
        for effect in self._effects:
            effect.begin()

    def update(self, delta_secs: float) -> bool:
        """Returns: True if program should terminate, falsy to continue"""
        results = []
        for effect in self._effects:
            is_playing = effect.update(delta_secs)
            results.append(is_playing)
        if not any(results):
            return True
        return False

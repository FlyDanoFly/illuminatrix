from copy import copy

from statemachine import State

from bases.BaseStateMachineEffect import BaseStateMachineEffect
from constants.constants import ColorType, ShouldStop, TowerEnum
from systems.SystemSingletonFactory import SystemSingletonFactory


class BingFade(BaseStateMachineEffect):
    start = State("start", initial=True)
    fading = State("fading")
    done = State("done", final=True)

    begin = start.to(fading)
    finish = fading.to(done)

    def __init__(
            self,
            towers_to_affect: list[TowerEnum],
            start_color: ColorType,
            end_color: ColorType,
            fade_time_sec: float,
            sustain_time_sec: float = 0.0,
    ) -> None:
        super().__init__()
        self._towers_to_affect = copy(towers_to_affect)

        self._start_color = start_color
        self._end_color = end_color
        self._fade_time_sec = fade_time_sec
        self._sustain_time_sec = sustain_time_sec

        self._elapsed_time = 0.0

    def attach_systems(self, system: SystemSingletonFactory) -> None:
        self._light_system = system.get_light_system()
        self._sound_system = system.get_sound_system()
        self._input_system = system.get_input_system()

    def is_playing(self) -> bool:
        return self.current_state != self.done

    def is_done(self) -> bool:
        return self.current_state == self.done

    def on_enter_fading(self) -> None:
        for tower_enum in self._towers_to_affect:
            self._light_system.set(tower_enum, self._start_color)

    def update(self, delta_secs: float) -> ShouldStop:
        """
        Returns
            bool - True if effect is still active
        """
        super().update(delta_secs)

        if self.current_state == self.start:
            self.begin()
            return False

        if self.current_state == self.done:
            return True

        self._elapsed_time += delta_secs

        if self._sustain_time_sec > 0.0 and self._elapsed_time < self._sustain_time_sec:
            # Still sustaining, not done yet
            return

        if self._elapsed_time >= (self._fade_time_sec + self._sustain_time_sec):
            self.finish()
            return

        factor = (self._elapsed_time - self._sustain_time_sec) / self._fade_time_sec
        new_color = (
            self._start_color[0] + factor * (self._end_color[0] - self._start_color[0]),
            self._start_color[1] + factor * (self._end_color[1] - self._start_color[1]),
            self._start_color[2] + factor * (self._end_color[2] - self._start_color[2]),
        )
        for tower_enum in self._towers_to_affect:
            self._light_system.set(tower_enum, new_color)


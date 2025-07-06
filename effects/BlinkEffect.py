from copy import copy

from statemachine import State

from bases.BaseStateMachineEffect import BaseStateMachineEffect
from constants.constants import ColorType, ShouldStop, TowerEnum
from systems.SystemSingletonFactory import SystemSingletonFactory


class BlinkEffect(BaseStateMachineEffect):
    start = State("high", initial=True)
    high = State("high")
    low = State("low")
    done = State("done", final=True)

    begin = start.to(high)
    cycle = high.to(low) | low.to(high)
    finish = high.to(done) | low.to(done)

    def __init__(
            self,
            towers_to_affect: list[TowerEnum],
            low_color: ColorType,
            high_color: ColorType,
            low_time_sec: float,
            high_time_sec: float,
            num_loops: int = 1,
    ) -> None:
        """
        Args
            num_loops: float - <=0 loop forever, positive integer means play that many times, TODO: default to 1
        """
        super().__init__()
        self._towers_to_affect = copy(towers_to_affect)

        self._low_color = low_color
        self._low_time_sec = low_time_sec

        self._high_color = high_color
        self._high_time_sec = high_time_sec

        self._num_loops = num_loops if num_loops > 0 else -1
        self._elapsed_time = 0.0
        self._time_to_change = 0.0

    def attach_systems(self, system: SystemSingletonFactory) -> None:
        self._light_system = system.get_light_system()
        self._sound_system = system.get_sound_system()
        self._input_system = system.get_input_system()

    def is_playing(self) -> bool:
        return self.current_state != self.done

    def is_done(self) -> bool:
        return self.current_state == self.done

    def on_enter_high(self) -> None:
        if self._num_loops == 0:
            self.finish()
            return
        self._time_to_change = self._high_time_sec
        for tower_enum in self._towers_to_affect:
            self._light_system.set(tower_enum, self._high_color)
            # self._towers[tower_enum].set_color(self._high_color)

    def on_enter_low(self) -> None:
        self._time_to_change = self._low_time_sec
        for tower_enum in self._towers_to_affect:
            self._light_system.set(tower_enum, self._low_color)
            # self._towers[tower_enum].set_color(self._low_color)

    def on_exit_low(self) -> None:
        self._num_loops -= 1

    def update(self, delta_secs: float) -> ShouldStop:
        """
        Returns
            bool - True if effect is still active
        """
        super().update(delta_secs)

        if self.current_state == self.done:
            return True

        self._elapsed_time += delta_secs
        if self._elapsed_time < self._time_to_change:
            return False

        if self._num_loops == 0:
            return True

        self._elapsed_time -= self._time_to_change
        self.cycle()
        return False


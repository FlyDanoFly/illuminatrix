"""Tests for the InputSystem base class: switch state, transitions, and
idle-time tracking, driven through a stub subclass (no hardware).

Runs two ways:

    poetry run pytest tests/
    poetry run python tests/test_input_system.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bases.InputSystem import InputSystem, SwitchKey  # noqa: E402
from constants.constants import ControllerSwitchEnum, TowerEnum  # noqa: E402

DT = 0.033  # one 30fps frame


class StubInputSystem(InputSystem):
    """Feed it the set of pressed switches for each upcoming update()."""

    def __init__(self):
        super().__init__()
        self.pressed: set[SwitchKey] = set()

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def render(self) -> None:
        pass

    def _read_switches(self, delta_secs: float) -> None:
        for switch in self.pressed:
            self._switch_state[switch] = True


def test_press_hold_release_transitions():
    system = StubInputSystem()
    system.update(DT)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1)

    system.pressed = {TowerEnum.Tower_1}
    system.update(DT)
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert system.did_tower_switch_transition_down(TowerEnum.Tower_1)
    assert not system.did_tower_switch_transition_up(TowerEnum.Tower_1)

    system.update(DT)  # still held: no fresh transition
    assert system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert not system.did_tower_switch_transition_down(TowerEnum.Tower_1)

    system.pressed = set()
    system.update(DT)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1)
    assert system.did_tower_switch_transition_up(TowerEnum.Tower_1)


def test_controller_queries_delegate_to_same_state():
    system = StubInputSystem()
    system.pressed = {ControllerSwitchEnum.START}
    system.update(DT)
    assert system.is_controller_switch_pressed(ControllerSwitchEnum.START)
    assert system.did_controller_switch_transition_down(ControllerSwitchEnum.START)
    assert not system.is_tower_switch_pressed(TowerEnum.Tower_1)


def test_idle_timers_grow_while_idle():
    system = StubInputSystem()
    for _ in range(3):
        system.update(DT)
    assert abs(system.secs_since_last_input - 3 * DT) < 1e-9
    assert abs(system.secs_since_last_tower_input - 3 * DT) < 1e-9
    assert abs(system.secs_since_last_controller_input - 3 * DT) < 1e-9


def test_tower_press_resets_tower_and_any_but_not_controller():
    system = StubInputSystem()
    system.update(DT)
    system.pressed = {TowerEnum.Tower_3}
    system.update(DT)
    assert system.secs_since_last_input == 0.0
    assert system.secs_since_last_tower_input == 0.0
    assert abs(system.secs_since_last_controller_input - 2 * DT) < 1e-9


def test_controller_press_resets_controller_and_any_but_not_tower():
    system = StubInputSystem()
    system.update(DT)
    system.pressed = {ControllerSwitchEnum.RESET}
    system.update(DT)
    assert system.secs_since_last_input == 0.0
    assert system.secs_since_last_controller_input == 0.0
    assert abs(system.secs_since_last_tower_input - 2 * DT) < 1e-9


def test_held_switch_keeps_resetting_idle_timer():
    # Someone standing on a pad is activity, even with no new transitions
    system = StubInputSystem()
    system.pressed = {TowerEnum.Tower_1}
    for _ in range(5):
        system.update(DT)
    assert system.secs_since_last_input == 0.0
    system.pressed = set()
    system.update(DT)
    assert abs(system.secs_since_last_input - DT) < 1e-9


if __name__ == "__main__":
    tests = [fn for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"{fn.__name__} OK")
    print(f"\nAll {len(tests)} tests passed")

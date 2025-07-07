from bases.InputSystem import InputSystem
from constants.constants import ControllerSwitchEnum, TowerEnum
from utils.KBHit import KBHit

# TODO: more modes? INSTANT vs HIGH UNTIL READ vs THIS_FRAME vs ??


class PrintInputSystem(InputSystem):
    def __init__(self):
        self._kbhit = KBHit()

    def startup(self) -> None:
        print("PrintInputSystem: startup")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintInputSystem: shutdown")
        return super().shutdown()

    def update(self, delta_secs: float) -> None: 
        print("PrintInputSystem: update", delta_secs)

    def render(self) -> None:
        print("PrintInputSystem: render")
        return super().render()

    def is_switch_pressed(self, switch: str) -> bool:
        print("PrintInputSystem.is_switch_pressed() called")
        return False

    def did_switch_transition_down(self, switch: str) -> bool:
        print("PrintInputSystem.did_switch_transition_down() called")
        return False

    def did_switch_transition_up(self, switch: str) -> bool:
        print("PrintInputSystem.did_switch_transition_up() called")
        return False

    def is_tower_switch_pressed(self, tower_enum: TowerEnum) -> bool:
        print("PrintInputSystem.is_tower_switch_pressed() called")
        return False

    def did_tower_switch_transition_down(self, tower_enum: TowerEnum) -> bool:
        print("PrintInputSystem.did_tower_switch_transition_down() called")
        return False

    def did_tower_switch_transition_up(self, tower_enum: TowerEnum) -> bool:
        print("PrintInputSystem.did_tower_switch_transition_up() called")
        return False

    def is_controller_switch_pressed(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        print("PrintInputSystem.is_controller_switch_pressed() called")
        return False

    def did_controller_switch_transition_down(self, _: ControllerSwitchEnum) -> bool:
        print("PrintInputSystem.did_controller_switch_transition_down() called")
        return False

    def did_controller_switch_transition_up(self, controller_switch_enum: ControllerSwitchEnum) -> bool:
        print("PrintInputSystem.did_controller_switch_transition_up() called")
        return False

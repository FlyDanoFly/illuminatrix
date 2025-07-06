from bases import BaseGame
from constants.constants import ShouldStop


class PrintGame(BaseGame):
    def __init__(self, *_) -> None:
        print("__init__ called")

    def first_frame_update(self) -> None:
        print("PrintGame: first_frame_update() called")

    def update(self, delta_secs: float) -> ShouldStop:
        print(f"PrintGame: update({delta_secs}) called")

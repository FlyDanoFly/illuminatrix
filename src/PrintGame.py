from BaseGame import BaseGame


class PrintGame(BaseGame):
    def first_frame_update(self) -> None:
        print("PrintGame: first_frame_update() called")
        return super().first_frame_update()

    def update(self, delta_ms: float) -> bool:
        print(f"PrintGame: update({delta_ms}) called")
        return super().update(delta_ms)

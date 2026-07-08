from bases.InputSystem import InputSystem


class PrintInputSystem(InputSystem):
    """Debug stub: prints lifecycle calls, reports no switches pressed."""

    def startup(self) -> None:
        print("PrintInputSystem: startup")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintInputSystem: shutdown")
        return super().shutdown()

    def _read_switches(self, delta_secs: float) -> None:
        print("PrintInputSystem: update", delta_secs)

    def render(self) -> None:
        print("PrintInputSystem: render")
        return super().render()

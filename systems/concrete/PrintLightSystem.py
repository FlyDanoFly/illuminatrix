from bases.LightSystem import LightSystem
from constants.constants import ColorType, LightPos, SystemIdentifier


class PrintLightSystem(LightSystem):
    def setup(self, num_towers: int):
        print(f"PrintLightSystem: Setting up {num_towers} towers")
        super().setup(num_towers)

    def set(self, system_id: SystemIdentifier, color: ColorType, light: LightPos=LightPos.All) -> None:
        print(f"PrintLightSystem: Setting tower {system_id} at pos {light} to {color}")
        return super().set(system_id, color, light)

    def update(self, delta_ms: float) -> None:
        print("PrintLightSystem: Updating the lights, json:")
        return super().update(delta_ms)

    def render(self):
        print("PrintLightSystem: Rendering the lights")
        return super().render()

    def startup(self) -> None:
        print("PrintLightSystem: Starting up the light system")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintLightSystem: Shutting down the light system")
        return super().shutdown()

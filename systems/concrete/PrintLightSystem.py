from bases.LightSystem import LightSystem
from constants.constants import ColorType, LightPos, TowerEnum


class PrintLightSystem(LightSystem):
    def setup(self):
        print("PrintLightSystem: Setting up towers")

    def set(self, tower_enum: TowerEnum, color: ColorType, light_pos: LightPos = LightPos.All) -> None:
        print(f"PrintLightSystem: Setting tower {tower_enum} at pos {light_pos} to {color}")
        return super().set(tower_enum, color, light_pos)

    def update(self, delta_secs: float) -> None:
        print("PrintLightSystem: Updating the lights, json:")
        return super().update(delta_secs)

    def render(self):
        print("PrintLightSystem: Rendering the lights")
        return super().render()

    def startup(self) -> None:
        print("PrintLightSystem: Starting up the light system")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintLightSystem: Shutting down the light system")
        return super().shutdown()

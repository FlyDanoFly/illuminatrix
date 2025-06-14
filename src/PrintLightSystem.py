from LightSystem import LightSystem
from constants import ColorType, LightPos, SystemIdentifier


class PrintLightSystem(LightSystem):
    def setup(self, num_towers: int):
        print(f"PrintLightSystem: Setting up {num_towers} towers")
        super().setup(num_towers)

    def set(self, system_id: SystemIdentifier, color: ColorType, light: LightPos=LightPos.All):
        print(f"PrintLightSystem: Setting tower {system_id} at pos {light} to {color}")
        super().set(system_id, color, light)

    def update(self, delta_ms: float):
        print("PrintLightSystem: Updating the lights, json:")

    def render(self):
        print("PrintLightSystem: Rendering the lights")

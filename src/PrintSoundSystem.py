from SoundSystem import SoundSystem
from constants import SystemIdentifier


class PrintSoundSystem(SoundSystem):
    def setup(self, num_towers: int):
        print(f"PrintSoundSystem: Setting up {num_towers} towers")
        super().setup(num_towers)

    def play(self, tower_id: SystemIdentifier, sound: str):
        print(f"PrintSoundSystem: Playing {sound} on tower {tower_id}")
        super().play(tower_id, sound)

    def update(self, delta_ms: float):
        print(f"PrintSoundSystem: Updating the sound, {delta_ms=} json:")

    def render(self):
        print("PrintSoundSystem: Rendering the sound")

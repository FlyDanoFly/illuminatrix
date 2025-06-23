from bases.SoundSystem import SoundSystem
from constants.constants import SystemIdentifier


class PrintSoundSystem(SoundSystem):
    def setup(self, num_towers: int, **_):
        print(f"PrintSoundSystem: Setting up {num_towers} towers")
        super().setup(num_towers)

    def play(self, tower_id: SystemIdentifier, sound: str) -> None:
        print(f"PrintSoundSystem: Playing {sound} on tower {tower_id}")
        return super().play(tower_id, sound)

    def update(self, delta_ms: float) -> None:
        print(f"PrintSoundSystem: Updating the sound, {delta_ms=} json:")
        return super().update(delta_ms)

    def render(self) -> None:
        print("PrintSoundSystem: Rendering the sound")
        return super().render()

    def startup(self) -> None:
        print("PrintSoundSystem: Starting up the sound system")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintSoundSystem: Shutting down the sound system")
        return super().shutdown()

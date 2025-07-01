from bases.SoundSystem import Sound, SoundSystem
from constants.constants import TowerEnum


class PrintSound(Sound):
    pass


class PrintSoundSystem(SoundSystem):
    def setup(self, **_):
        print("PrintSoundSystem: Setting up towers")

    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound:
        print(f"PrintSoundSystem: Playing {sound} on tower {tower_enums} for {num_loops} times")
        return super().play(sound, tower_enums, volume, num_loops)

    def update(self, delta_secs: float) -> None:
        print(f"PrintSoundSystem: Updating the sound, {delta_secs=} json:")
        return super().update(delta_secs)

    def render(self) -> None:
        print("PrintSoundSystem: Rendering the sound")
        return super().render()

    def startup(self) -> None:
        print("PrintSoundSystem: Starting up the sound system")
        return super().startup()

    def shutdown(self) -> None:
        print("PrintSoundSystem: Shutting down the sound system")
        return super().shutdown()

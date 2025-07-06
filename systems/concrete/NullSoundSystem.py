
from bases.SoundSystem import Sound, SoundSystem
from constants.constants import TowerEnum


class NullSoundSystem(SoundSystem):
    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound:
        return super().play(sound, tower_enums)

    def update(self, delta_secs: float):
        return super().update(delta_secs)

    def render(self):
        return super().render()

    def startup(self):
        return super().startup()

    def shutdown(self):
        return super().shutdown()

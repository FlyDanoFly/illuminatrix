
from constants import SystemIdentifier
from SoundSystem import SoundSystem


class NullSoundSystem(SoundSystem):
    def play(self, tower_id: SystemIdentifier, sound: str):
        return super().play(tower_id, sound)

    def update(self, delta_ms: float):
        return super().update(delta_ms)

    def render(self):
        return super().render()

    def startup(self):
        return super().startup()

    def shutdown(self):
        return super().shutdown()

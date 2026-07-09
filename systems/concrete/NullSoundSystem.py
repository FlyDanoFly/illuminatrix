from bases.SoundSystem import NullSound, Sound, SoundSystem
from constants.constants import TowerEnum


class NullSoundSystem(SoundSystem):
    """Fully silent sound system — run the installation without audio
    (e.g. hardware debugging) with no JACK server and no console noise."""

    def __init__(self, **_):
        # Tolerates context keys meant for other sound systems
        super().__init__()

    def load_sound_bank(self, path: str) -> None:
        pass

    def play(self, sound: str, tower_enums: list[TowerEnum] | None = None, volume: float = 1.0, num_loops: int = 0) -> Sound:
        return NullSound()

    def stop_all(self, fade_secs: float = 0.25) -> None:
        pass

    def are_any_sounds_playing(self) -> bool:
        return False

    def update(self, delta_secs: float) -> None:
        pass

    def render(self) -> None:
        pass

    def startup(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

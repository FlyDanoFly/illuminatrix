from constants import ColorType, LightPos, TowerEnum
from LightSystem import LightSystem
from SoundSystem import SoundSystem


class Tower:
    def __init__(self, tower_enum: TowerEnum, system_identifier, light_system: LightSystem, sound_system: SoundSystem):
        self.tower = tower_enum
        self.system_identifier = system_identifier
        self.light_system = light_system
        self.sound_system = sound_system

    def set_color(self, color: ColorType, light: LightPos = LightPos.All):
        self.light_system.set(self.system_identifier, color, light)

    def play_sound(self, sound):
        self.sound_system.play(self.system_identifier, sound)

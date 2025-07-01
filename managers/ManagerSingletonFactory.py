from managers.EffectManager import EffectManager
from systems.SystemSingletonFactory import SystemSingletonFactory


class ManagerSingletonFactory:
    _effects: EffectManager

    def __init__(self, system: SystemSingletonFactory):
        self._system = system

        self._effects: EffectManager = EffectManager(self._system)

    def get_effect_manager(self) -> EffectManager:
        return self._effects

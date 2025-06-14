from abc import ABC, abstractmethod


class BaseSystem(ABC):
    @abstractmethod
    def setup(self, num_towers: int) -> None:
        pass

    @abstractmethod
    def update(self, delta_ms: float) -> None:
        pass

    @abstractmethod
    def render(self) -> None:
        pass


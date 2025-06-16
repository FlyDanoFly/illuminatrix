from abc import ABC, abstractmethod


class BaseSystem(ABC):
    @abstractmethod
    def startup(self) -> None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass

    @abstractmethod
    def update(self, delta_ms: float) -> None:
        pass

    @abstractmethod
    def render(self) -> None:
        pass


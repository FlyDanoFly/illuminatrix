import logging

from statemachine import Event

from constants.constants import ShouldStop

logger = logging.getLogger(__name__)


class StateMachineMixin:
    """Adds behavior to call do_{state} on every update"""
    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        super().update(delta_secs)
        return self._do_state(delta_secs)

    def _do_state(self, delta_secs: float) -> ShouldStop:
        if do_state := getattr(self, f'do_{self.current_state.value}', None):
            return do_state(delta_secs)

    def on_transition(self, event_data, event: Event) -> None:
        logging.debug(
            "%s transitioning from %s to %s",
            self.__class__,
            event_data.transition.source.id,
            event_data.transition.target.id,
        )

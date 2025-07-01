from constants.constants import ShouldStop


class StateMachineMixin:
    """Adds behavior to call do_{state} on every update"""
    def update(self, delta_secs: float) -> ShouldStop:
        """Returns: True if program should terminate, falsy to continue"""
        super().update(delta_secs)
        return self._do_state(delta_secs)

    def _do_state(self, delta_secs: float) -> ShouldStop:
        if do_state := getattr(self, f'do_{self.current_state.value}', None):
            return do_state(delta_secs)

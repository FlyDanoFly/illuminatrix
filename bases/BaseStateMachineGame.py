from statemachine import StateMachine

from bases import BaseGame
from bases.ABCStateMachineMeta import ABCStateMachineMeta
from bases.StateMachineMixin import StateMachineMixin


class BaseStateMachineGame(StateMachineMixin, StateMachine, BaseGame, metaclass=ABCStateMachineMeta):
    """Base class for games using a state machine."""

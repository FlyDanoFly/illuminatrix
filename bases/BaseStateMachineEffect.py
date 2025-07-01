from statemachine.statemachine import StateMachine

from bases.ABCStateMachineMeta import ABCStateMachineMeta
from bases.BaseEffect import BaseEffect
from bases.BaseStateMachineGame import StateMachineMixin


class BaseStateMachineEffect(StateMachineMixin, StateMachine, BaseEffect, metaclass=ABCStateMachineMeta):
    pass

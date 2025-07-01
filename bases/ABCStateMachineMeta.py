from abc import ABCMeta

from statemachine import StateMachine


class ABCStateMachineMeta(ABCMeta, type(StateMachine)):
    """This class exists to allow an Abstract Base Class to mix with a StateMachine"""
    pass


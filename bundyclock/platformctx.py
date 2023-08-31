from abc import ABC, abstractmethod


class PunchStrategy(ABC):
    """
    Base class for punch time strategy. Typically implemented as checking
    lockscreen status.
    Invoked by the PlatformCtx class.
    """
    @abstractmethod
    def __init__(self, **kwargs):
        pass

    @abstractmethod
    def run(self):
        pass


class PlatformCtx():
    """
    Base class for interaction with main loops for checking automatic in/out times
    """

    def __init__(self, strategy: PunchStrategy) -> None:
        self._strategy = strategy

    @property
    def strategy(self) -> PunchStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: PunchStrategy) -> None:
        self._strategy = strategy

    def run(self) -> None:
        self._strategy.run()

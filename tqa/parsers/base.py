from abc import ABC, abstractmethod
from tqa.models import ComponentReport


class Parser(ABC):
    @abstractmethod
    def parse(self, path: str, report: ComponentReport) -> ComponentReport:
        ...

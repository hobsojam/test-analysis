from abc import ABC, abstractmethod
from tqa.models import ProjectReport


class Parser(ABC):
    @abstractmethod
    def parse(self, path: str, report: ProjectReport) -> ProjectReport:
        ...

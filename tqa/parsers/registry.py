from typing import Dict, List, Type
from tqa.parsers.base import Parser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: Dict[str, Type[Parser]] = {}

    def register(self, name: str, cls: Type[Parser]) -> None:
        self._parsers[name] = cls

    def get(self, name: str) -> Parser:
        return self._parsers[name]()

    def names(self) -> List[str]:
        return list(self._parsers.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._parsers


registry = ParserRegistry()


def register_parser(name: str):
    def decorator(cls: Type[Parser]) -> Type[Parser]:
        registry.register(name, cls)
        return cls
    return decorator

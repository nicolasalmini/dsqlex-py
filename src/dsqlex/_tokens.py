from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Token:
    type: str
    value: Any = None

    def __repr__(self) -> str:
        if self.value is None:
            return f"Token({self.type!r})"
        return f"Token({self.type!r}, {self.value!r})"

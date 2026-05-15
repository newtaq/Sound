from __future__ import annotations


class RuntimeDictionary:
    def __init__(self, values: list[str] | None = None) -> None:
        self.values = values or []

    def get_all(self) -> list[str]:
        return list(self.values)
    
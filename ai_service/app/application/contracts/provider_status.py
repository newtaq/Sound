from dataclasses import dataclass


@dataclass(slots=True)
class AIProviderStatus:
    available: bool = True
    reason: str | None = None
    


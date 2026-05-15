from dataclasses import dataclass


@dataclass(slots=True)
class AIProviderRoutingConfig:
    enable_fallback: bool = True
    stream_fallback_to_generate: bool = True
    


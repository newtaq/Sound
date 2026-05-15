from dataclasses import dataclass


@dataclass(slots=True)
class AIProviderLimits:
    max_text_length: int | None = None
    max_media_count: int = 0
    max_media_caption_length: int | None = None
    max_message_count_per_request: int | None = None
    one_active_request_per_session: bool = True
    send_large_text_as_file: bool = False
    request_timeout_seconds: float | None = None
    retry_count: int = 0
    retry_delay_seconds: float = 0.0
    


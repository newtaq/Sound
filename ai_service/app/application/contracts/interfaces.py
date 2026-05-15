from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.application.contracts.limits import AIProviderLimits
from app.application.contracts.models import (
    AIProviderCapabilities,
    AIRequest,
    AIResponse,
    AIStreamChunk,
)
from app.application.contracts.provider_status import AIProviderStatus


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def capabilities(self) -> AIProviderCapabilities:
        raise NotImplementedError

    @property
    @abstractmethod
    def limits(self) -> AIProviderLimits:
        raise NotImplementedError

    @property
    def status(self) -> AIProviderStatus:
        return AIProviderStatus(available=True)

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        raise NotImplementedError


class StreamingAIProvider(AIProvider, ABC):
    @abstractmethod
    def stream(self, request: AIRequest) -> AsyncIterator[AIStreamChunk]:
        raise NotImplementedError
    


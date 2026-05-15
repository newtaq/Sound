from __future__ import annotations

from typing import Protocol

from app.domain.posters.entities.poster_input import PostImageInput
from app.infrastructure.posters.ocr import PosterImage


class PosterImageLoader(Protocol):
    async def load(self, image: PostImageInput) -> PosterImage | None:
        ...
        
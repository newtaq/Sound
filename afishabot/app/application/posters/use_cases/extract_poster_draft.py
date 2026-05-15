from __future__ import annotations

from app.application.posters.interfaces.poster_image_loader import PosterImageLoader
from app.application.posters.interfaces.poster_ocr import PosterOCRService
from app.domain.posters.entities.poster_draft import PosterDraft
from app.domain.posters.entities.poster_input import PosterInput
from app.infrastructure.posters.extractors.generic_poster_extractor import (
    GenericPosterExtractor,
)
from app.infrastructure.posters.ocr import PosterOCRContext, PosterOCRRequest


class ExtractPosterDraftUseCase:
    def __init__(
        self,
        extractor: GenericPosterExtractor | None = None,
        ocr_service: PosterOCRService | None = None,
        image_loader: PosterImageLoader | None = None,
    ) -> None:
        self._extractor = extractor or GenericPosterExtractor()
        self._ocr_service = ocr_service
        self._image_loader = image_loader

    @property
    def ocr_service(self) -> PosterOCRService | None:
        return self._ocr_service

    @property
    def image_loader(self) -> PosterImageLoader | None:
        return self._image_loader

    def execute(self, data: PosterInput) -> PosterDraft:
        return self._extractor.extract(data)

    async def execute_with_ocr(self, data: PosterInput) -> PosterDraft:
        ocr_service = self._ocr_service
        image_loader = self._image_loader

        if ocr_service is None or image_loader is None:
            return self.execute(data)

        ocr_text = await self._extract_ocr_text(
            data=data,
            ocr_service=ocr_service,
            image_loader=image_loader,
        )

        if not ocr_text:
            return self.execute(data)

        enriched_input = self._merge_ocr_text(data, ocr_text)
        return self._extractor.extract(enriched_input)

    async def _extract_ocr_text(
        self,
        data: PosterInput,
        ocr_service: PosterOCRService,
        image_loader: PosterImageLoader,
    ) -> str | None:
        for image_input in sorted(data.images, key=self._image_sort_key):
            poster_image = await image_loader.load(image_input)
            if poster_image is None:
                continue

            request = PosterOCRRequest(
                image=poster_image,
                context=self._build_ocr_context(data),
                debug=False,
            )
            result = await ocr_service.recognize(request)

            text = result.normalized_text.strip() or result.raw_text.strip()
            if text:
                return text

        return None

    def _build_ocr_context(self, data: PosterInput) -> PosterOCRContext:
        description_parts: list[str] = []

        title = data.title.strip()
        if title:
            description_parts.append(title)

        if data.text:
            text = data.text.strip()
            if text:
                description_parts.append(text)

        description_text = "\n".join(description_parts).strip() or None

        return PosterOCRContext(
            description_text=description_text,
            entity_candidates=[],
            extra={
                "channel_id": data.channel_id,
                "post_id": data.post_id,
            },
        )

    def _merge_ocr_text(self, data: PosterInput, ocr_text: str) -> PosterInput:
        base_parts: list[str] = []

        if data.text:
            text = data.text.strip()
            if text:
                base_parts.append(text)

        if ocr_text.strip():
            base_parts.append(ocr_text.strip())

        merged_text = "\n\n".join(base_parts).strip() or None

        return PosterInput(
            title=data.title,
            text=merged_text,
            html_text=data.html_text,
            buttons=list(data.buttons),
            images=list(data.images),
            channel_id=data.channel_id,
            post_id=data.post_id,
            published_at=data.published_at,
        )

    def _image_sort_key(self, image: object) -> tuple[int, int]:
        position = getattr(image, "position", None)
        width = getattr(image, "width", None) or 0
        height = getattr(image, "height", None) or 0
        area = width * height

        normalized_position = position if isinstance(position, int) else 10**9
        return (normalized_position, -area)
    
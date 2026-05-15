from dataclasses import replace

from app.application.contracts import AIMedia, AIRequest, AITextFile
from app.application.message_splitter import AIMessagePart, AIMessageSplitter


class AIProviderRequestBuilder:
    def __init__(self, message_splitter: AIMessageSplitter | None = None) -> None:
        self._message_splitter = message_splitter or AIMessageSplitter()

    def build_parts(
        self,
        request: AIRequest,
        max_text_length: int | None,
        send_large_text_as_file: bool = False,
        max_media_count: int | None = None,
    ) -> list[AIRequest]:
        text_parts = self._build_text_parts(
            request=request,
            max_text_length=max_text_length,
            send_large_text_as_file=send_large_text_as_file,
        )

        result: list[AIRequest] = []
        for text_part in text_parts:
            result.extend(
                self._build_media_parts(
                    request=text_part,
                    max_media_count=max_media_count,
                )
            )

        return result

    def _build_text_parts(
        self,
        request: AIRequest,
        max_text_length: int | None,
        send_large_text_as_file: bool,
    ) -> list[AIRequest]:
        if (
            send_large_text_as_file
            and max_text_length is not None
            and len(request.text) > max_text_length
        ):
            return [self._build_file_request(request)]

        parts = self._message_splitter.split(
            text=request.text,
            max_length=max_text_length,
        )

        if len(parts) == 1:
            return [request]

        return [
            replace(
                request,
                text=self._format_part(part),
                metadata={
                    **request.metadata,
                    "is_multipart": True,
                    "part_index": part.index,
                    "part_total": part.total,
                },
            )
            for part in parts
        ]

    def _build_media_parts(
        self,
        request: AIRequest,
        max_media_count: int | None,
    ) -> list[AIRequest]:
        if max_media_count is None:
            return [request]

        if max_media_count <= 0:
            return [request]

        if len(request.media) <= max_media_count:
            return [request]

        chunks = self._split_media(
            media=request.media,
            max_media_count=max_media_count,
        )

        return [
            replace(
                request,
                media=chunk,
                metadata={
                    **request.metadata,
                    "is_media_multipart": True,
                    "media_part_index": index,
                    "media_part_total": len(chunks),
                },
            )
            for index, chunk in enumerate(chunks, start=1)
        ]

    def _split_media(
        self,
        media: list[AIMedia],
        max_media_count: int,
    ) -> list[list[AIMedia]]:
        return [
            media[index:index + max_media_count]
            for index in range(0, len(media), max_media_count)
        ]

    def _build_file_request(self, request: AIRequest) -> AIRequest:
        filename = self._build_text_filename(request)

        return replace(
            request,
            text=(
                "The full request text is attached as a .txt file. "
                "Read the file and process it as the main request."
            ),
            text_files=[
                *request.text_files,
                AITextFile(
                    filename=filename,
                    content=request.text,
                ),
            ],
            metadata={
                **request.metadata,
                "large_text_as_file": True,
                "large_text_filename": filename,
            },
        )

    def _build_text_filename(self, request: AIRequest) -> str:
        session_id = request.session_id or "request"
        safe_session_id = "".join(
            char if char.isalnum() or char in ("-", "_") else "_"
            for char in session_id
        )
        return f"{safe_session_id}_request.txt"

    def _format_part(self, part: AIMessagePart) -> str:
        if part.index < part.total:
            return (
                f"[PART {part.index}/{part.total}]\n"
                "Do not answer yet. Wait for all parts.\n\n"
                f"{part.text}"
            )

        return (
            f"[PART {part.index}/{part.total}]\n"
            "This is the final part. Now process the full request.\n\n"
            f"{part.text}"
        )
        


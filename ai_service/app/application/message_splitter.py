from dataclasses import dataclass


@dataclass(slots=True)
class AIMessagePart:
    index: int
    total: int
    text: str


class AIMessageSplitter:
    def split(self, text: str, max_length: int | None) -> list[AIMessagePart]:
        if max_length is None or len(text) <= max_length:
            return [
                AIMessagePart(
                    index=1,
                    total=1,
                    text=text,
                )
            ]

        if max_length <= 0:
            raise ValueError("max_length must be positive")

        chunks: list[str] = []
        current = text.strip()

        while current:
            if len(current) <= max_length:
                chunks.append(current)
                break

            split_at = self._find_split_position(current, max_length)
            chunks.append(current[:split_at].rstrip())
            current = current[split_at:].lstrip()

        total = len(chunks)

        return [
            AIMessagePart(
                index=index + 1,
                total=total,
                text=chunk,
            )
            for index, chunk in enumerate(chunks)
        ]

    def _find_split_position(self, text: str, max_length: int) -> int:
        candidates = [
            text.rfind("\n", 0, max_length),
            text.rfind(". ", 0, max_length),
            text.rfind(", ", 0, max_length),
            text.rfind(" ", 0, max_length),
        ]

        for candidate in candidates:
            if candidate > max_length // 2:
                return candidate + 1

        return max_length
    


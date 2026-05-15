import asyncio
import json
import struct
import zlib
from pathlib import Path

from app.application.contracts import AIMedia, AIMediaType, AIMode
from app.infrastructure.service_factory import build_ai_client


def make_png(width: int = 64, height: int = 64) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw_rows = []

    for y in range(height):
        row = bytearray()
        row.append(0)

        for x in range(width):
            if x < width // 2:
                row.extend((240, 40, 40))
            else:
                row.extend((40, 90, 240))

        raw_rows.append(bytes(row))

    raw = b"".join(raw_rows)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def ensure_test_image() -> Path:
    path = Path(".runtime/tests/groq_vision_test.png")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(make_png())
    return path


async def main() -> None:
    image_path = ensure_test_image()

    client = build_ai_client(
        provider_names=[
            "groq_vision",
        ]
    )

    response = await client.ask(
        text=(
            "Посмотри на изображение. Ответь коротко: "
            "какие основные цвета на нём видны?"
        ),
        provider_name="groq_vision",
        mode=AIMode.FAST,
        session_id="groq-vision-smoke-test",
        media=[
            AIMedia(
                media_type=AIMediaType.IMAGE,
                path=str(image_path),
                mime_type="image/png",
                filename="groq_vision_test.png",
            )
        ],
        use_history=False,
        save_history=False,
        metadata={
            "script": "test_groq_vision",
        },
    )

    print("STATUS:", response.status.value)
    print("PROVIDER:", response.provider_name)
    print("REQUEST:", response.request_id)
    print("SESSION:", response.session_id)
    print("ERROR:", response.error)
    print()
    print("TEXT:")
    print(response.text)
    print()
    print("METADATA:")
    print(
        json.dumps(
            response.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    assert response.status.value == "ok"
    assert response.provider_name == "groq_vision"
    assert response.metadata.get("media_count") == 1
    assert response.text.strip()

    print()
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())

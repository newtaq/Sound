import asyncio
import json

from app.application.contracts import AIRequest
from app.infrastructure.providers.mira import MiraTelegramProvider


async def main() -> None:
    provider = MiraTelegramProvider()

    long_text = "\n".join(
        [
            "Это тест длинного текста для Telegram-провайдера Миры.",
            "Нужно проверить, что текст отправится как .txt файл.",
            "",
            *[
                f"Строка {index}: тестовые данные для анализа."
                for index in range(1, 250)
            ],
        ]
    )

    request = AIRequest(
        text=(
            "Прочитай длинный текст из вложенного .txt файла. "
            "Ответь одной короткой фразой: сколько примерно строк было в файле?"
            "\n\n"
            + long_text
        ),
        session_id="mira-long-text-smoke-test",
        instructions="Отвечай очень кратко.",
        response_format="plain_text",
    )

    response = await provider.generate(request)

    print("STATUS:", response.status)
    print("PROVIDER:", response.provider_name)
    print("SESSION:", response.session_id)

    if response.error:
        print("ERROR:", response.error)

    print("\nTEXT:")
    print(response.text)

    print("\nMETADATA:")
    print(
        json.dumps(
            response.metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
    

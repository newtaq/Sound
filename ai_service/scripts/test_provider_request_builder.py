from app.application.contracts import AIRequest
from app.application.provider_request_builder import AIProviderRequestBuilder


def main() -> None:
    builder = AIProviderRequestBuilder()

    request = AIRequest(
        text=(
            "Первая часть длинного сообщения. "
            "Вторая часть длинного сообщения. "
            "Третья часть длинного сообщения. "
            "Четвертая часть длинного сообщения."
        ),
        session_id="split-test-1",
        provider_name="mock",
    )

    parts = builder.build_parts(request=request, max_text_length=80)

    for part in parts:
        print("=" * 30)
        print(part.metadata)
        print(part.text)


if __name__ == "__main__":
    main()
    

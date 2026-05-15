from app.infrastructure.providers import build_ai_provider


def main() -> None:
    groq = build_ai_provider("groq")
    groq_search = build_ai_provider("groq_search")
    groq_vision = build_ai_provider("groq_vision")

    assert groq.name == "groq"
    assert groq.capabilities.can_stream is True
    assert groq.capabilities.can_analyze_images is False
    assert groq.capabilities.can_search_web_natively is False

    assert groq_search.name == "groq_search"
    assert groq_search.capabilities.can_stream is True
    assert groq_search.capabilities.can_analyze_images is False
    assert groq_search.capabilities.can_search_web_natively is True

    assert groq_vision.name == "groq_vision"
    assert groq_vision.capabilities.can_stream is True
    assert groq_vision.capabilities.can_analyze_images is True
    assert groq_vision.capabilities.can_search_web_natively is False
    assert groq_vision.capabilities.max_media_count == 5

    print("ok")


if __name__ == "__main__":
    main()

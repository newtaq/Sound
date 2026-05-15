from app.application.cache import AIAnalysisCacheKeyBuilder
from app.application.contracts import AIContentInput


def main() -> None:
    builder = AIAnalysisCacheKeyBuilder()

    content = AIContentInput(
        text="Кишлак. Тур 2026. 12 мая — Москва.",
        source_type="social_post",
        source_platform="telegram",
        source_item_id="cache-key-post-1",
    )

    same_content = AIContentInput(
        text="Кишлак. Тур 2026. 12 мая — Москва.",
        source_type="social_post",
        source_platform="telegram",
        source_item_id="cache-key-post-1",
    )

    changed_content = AIContentInput(
        text="Кишлак. Тур 2026. 14 мая — Санкт-Петербург.",
        source_type="social_post",
        source_platform="telegram",
        source_item_id="cache-key-post-1",
    )

    key_1 = builder.build_content_key(content)
    key_2 = builder.build_content_key(same_content)
    key_3 = builder.build_content_key(content, provider_name="content_mock")
    key_4 = builder.build_content_key(changed_content)

    print("KEY 1:", key_1)
    print("KEY 2:", key_2)
    print("KEY 3:", key_3)
    print("KEY 4:", key_4)

    print("SAME CONTENT SAME KEY:", key_1 == key_2)
    print("PROVIDER CHANGES KEY:", key_1 != key_3)
    print("TEXT CHANGES KEY:", key_1 != key_4)

    if key_1 != key_2:
        raise SystemExit("Same content produced different cache keys")

    if key_1 == key_3:
        raise SystemExit("Provider name did not change cache key")

    if key_1 == key_4:
        raise SystemExit("Changed content did not change cache key")


if __name__ == "__main__":
    main()
    

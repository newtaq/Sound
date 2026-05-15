from app.application.poster_agent.event_summary_renderer import (
    PosterEventSummaryRenderer,
)


def main() -> None:
    renderer = PosterEventSummaryRenderer()

    text = renderer.render(
        {
            "title": "Pepel Nahudi",
            "event_type": "concert",
            "artists": ["Pepel Nahudi"],
            "age_limit": 16,
            "description": "Сольный концерт Pepel Nahudi",
            "occurrences": [
                {
                    "city_name": "Санкт-Петербург",
                    "venue_name": "Муз Порт",
                    "address": "площадь Морской Славы, 1",
                    "event_date": "20 августа",
                    "start_time": None,
                    "doors_time": None,
                    "verified": True,
                    "source_url": "https://red-summer.ru",
                    "explanation": "Дата, город и площадка подтверждены прямым чтением URL.",
                }
            ],
            "links": [
                {
                    "url": "https://clck.ru/3THNTP",
                    "kind": "ticket",
                    "title": "TicketsCloud",
                    "verified": False,
                    "source_type": "url",
                    "explanation": "Ссылка раскрылась до билетного сервиса, но страница не содержит достаточно фактов события.",
                },
                {
                    "url": "https://red-summer.ru/spb",
                    "kind": "official",
                    "title": "Официальный сайт Red Summer",
                    "verified": True,
                    "source_type": "url",
                    "explanation": "Ссылка подтверждена прямым чтением URL.",
                },
            ],
            "facts": [
                {
                    "field": "artist",
                    "value": "Pepel Nahudi",
                    "status": "verified",
                    "source_type": "url",
                    "confidence": 1.0,
                    "source_url": "https://red-summer.ru",
                    "source_title": "RED SUMMER 2026",
                    "explanation": "Факт подтверждён прямым чтением URL.",
                },
                {
                    "field": "date",
                    "value": "20 августа",
                    "status": "verified",
                    "source_type": "url",
                    "confidence": 0.9,
                    "source_url": "https://red-summer.ru",
                    "source_title": "RED SUMMER 2026",
                    "explanation": "Факт подтверждён прямым чтением URL.",
                },
                {
                    "field": "city",
                    "value": "Санкт-Петербург",
                    "status": "verified",
                    "source_type": "url",
                    "confidence": 1.0,
                    "source_url": "https://red-summer.ru",
                    "source_title": "RED SUMMER 2026",
                    "explanation": "Факт подтверждён прямым чтением URL.",
                },
                {
                    "field": "venue",
                    "value": "Муз Порт",
                    "status": "verified",
                    "source_type": "url",
                    "confidence": 1.0,
                    "source_url": "https://red-summer.ru",
                    "source_title": "RED SUMMER 2026",
                    "explanation": "Факт подтверждён прямым чтением URL.",
                },
                {
                    "field": "age_limit",
                    "value": "16",
                    "status": "unverified",
                    "source_type": "ocr",
                    "confidence": 0.5,
                    "source_url": None,
                    "source_title": None,
                    "explanation": "из афиши, не подтверждено внешним источником",
                },
                {
                    "field": "price",
                    "value": "от 2300 ₽",
                    "status": "unverified",
                    "source_type": "input_text",
                    "confidence": 0.5,
                    "source_url": None,
                    "source_title": None,
                    "explanation": "из текста, не подтверждено",
                },
            ],
            "missing_fields": [],
            "conflicts": [],
            "warnings": [],
            "overall_confidence": 0.75,
            "recommendation": "needs_review",
        },
        status="needs_review",
    )

    assert "🎫 Афиша: Pepel Nahudi" in text
    assert "Статус: нужна проверка" in text
    assert "✅ Тип: концерт" in text
    assert "✅ Артист: Pepel Nahudi" in text
    assert "✅ Дата: 20 августа" in text
    assert "✅ Город: Санкт-Петербург" in text
    assert "✅ Площадка: Муз Порт" in text
    assert "✅ Адрес: площадь Морской Славы, 1" in text
    assert "⚠️ Возраст: 16+" in text
    assert "⚠️ Цена: от 2300 ₽" in text
    assert "⚠️ Билеты: https://clck.ru/3THNTP" in text
    assert "✅ Официальный источник: https://red-summer.ru/spb" in text
    assert "Что подтверждено:" not in text
    assert "Что не подтверждено:" not in text
    assert "Итоговый пост:" not in text

    print("ok")


if __name__ == "__main__":
    main()
    
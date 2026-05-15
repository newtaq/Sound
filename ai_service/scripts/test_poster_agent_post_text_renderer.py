from app.application.poster_agent.post_text_renderer import PosterPostTextRenderer


def main() -> None:
    renderer = PosterPostTextRenderer()

    event = {
        "title": "Pepel Nahudi",
        "event_type": "concert",
        "artists": ["Pepel Nahudi"],
        "age_limit": 16,
        "description": "Большой летний концерт.",
        "occurrences": [
            {
                "city_name": "Санкт-Петербург",
                "venue_name": "Муз Порт",
                "event_date": "20 августа",
                "doors_time": "19:00",
                "start_time": "20:00",
            }
        ],
        "links": [
            {
                "url": "https://clck.ru/3THNTP",
                "kind": "ticket",
            },
            {
                "url": "https://red-summer.ru",
                "kind": "official",
            },
            {
                "url": "https://t.me/example",
                "kind": "social",
            },
        ],
    }

    text = renderer.render(event)

    assert text.startswith("Pepel Nahudi")
    assert "Большой летний концерт." in text
    assert "20 августа" in text
    assert "Санкт-Петербург — Муз Порт" in text
    assert "Двери: 19:00" in text
    assert "Начало: 20:00" in text
    assert "16+" in text
    assert "Билеты: https://clck.ru/3THNTP" in text
    assert "Подробнее: https://red-summer.ru" in text
    assert "Соцсети: https://t.me/example" in text

    wrapped_text = renderer.render(
        {
            "poster_verification": event,
        }
    )

    assert wrapped_text == text

    multi_day_event = {
        "title": "Фестиваль",
        "artists": ["Артист 1", "Артист 2"],
        "occurrences": [
            {
                "city_name": "Санкт-Петербург",
                "venue_name": "Муз Порт",
                "event_date": "20 августа",
            },
            {
                "city_name": "Москва",
                "venue_name": "Base",
                "event_date": "21 августа",
                "start_time": "20:30",
            },
        ],
        "links": [],
    }

    multi_day_text = renderer.render(multi_day_event)

    assert "Фестиваль" in multi_day_text
    assert "Артист 1, Артист 2" in multi_day_text
    assert "Даты:" in multi_day_text
    assert "• 20 августа — Санкт-Петербург — Муз Порт" in multi_day_text
    assert "• 21 августа — Москва — Base (начало 20:30)" in multi_day_text

    custom_template = (
        "{title}\n\n"
        "{artists}\n\n"
        "{occurrences}\n\n"
        "Билеты тут: {ticket_url}"
    )

    custom_text = renderer.render(event, template=custom_template)

    assert "Pepel Nahudi" in custom_text
    assert "20 августа" in custom_text
    assert "Билеты тут: https://clck.ru/3THNTP" in custom_text

    print("ok")


if __name__ == "__main__":
    main()
    
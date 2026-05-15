from __future__ import annotations

import asyncio
import html
from datetime import datetime

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message

from app.application.posters.use_cases.extract_poster_draft import (
    ExtractPosterDraftUseCase,
)
from app.domain.posters.entities.poster_input import (
    PosterInput,
)


TOKEN = "8798460016:AAGy8FA5Blmkno3t1UosRVB2ND3dOkJXIpg"


def build_poster_input_from_message(message: Message) -> PosterInput | None:
    text = (message.text or message.caption or "").strip()
    html_text = (message.html_text or "").strip() or None

    if not text and not html_text:
        return None

    return PosterInput(
        text=text,
        html_text=html_text,
        buttons=[],
        images=[],
        channel_id=message.chat.id if message.chat else None,
        post_id=message.message_id,
        published_at=message.date if isinstance(message.date, datetime) else None,
    )


def format_poster_draft(poster_draft: object) -> str:
    title = getattr(poster_draft, "title", None)
    artist_names = getattr(poster_draft, "artist_names", None) or []
    organizer_names = getattr(poster_draft, "organizer_names", None) or []
    occurrences = getattr(poster_draft, "occurrences", None) or []
    age_limit = getattr(poster_draft, "age_limit", None)
    promo_codes = getattr(poster_draft, "promo_codes", None) or []
    description = getattr(poster_draft, "description", None)
    ticket_links = getattr(poster_draft, "ticket_links", None) or []
    chat_links = getattr(poster_draft, "chat_links", None) or []
    external_links = getattr(poster_draft, "external_links", None) or []

    lines: list[str] = []
    lines.append("🎫 <b>Афиша</b>")
    lines.append("")

    if title:
        lines.append(f"🎵 <b>{html.escape(str(title))}</b>")

    if artist_names:
        lines.append(
            f"👤 <b>Артисты:</b> {html.escape(', '.join(map(str, artist_names)))}"
        )

    if organizer_names:
        lines.append(
            f"🛠 <b>Организаторы:</b> {html.escape(', '.join(map(str, organizer_names)))}"
        )

    for occurrence in occurrences:
        city_name = getattr(occurrence, "city_name", None)
        venue_name = getattr(occurrence, "venue_name", None)
        address = getattr(occurrence, "address", None)
        event_date = getattr(occurrence, "event_date", None)
        timings = getattr(occurrence, "timings", None) or []

        if event_date:
            try:
                lines.append(f"📅 <b>Дата:</b> {event_date.strftime('%d.%m.%Y')}")
            except Exception:
                lines.append(f"📅 <b>Дата:</b> {html.escape(str(event_date))}")

        if timings:
            time_parts: list[str] = []
            for timing in timings:
                label = getattr(timing, "label", None)
                time_value = getattr(timing, "time", None)

                if time_value is None:
                    continue

                try:
                    time_text = time_value.strftime("%H:%M")
                except Exception:
                    time_text = str(time_value)

                if label:
                    time_parts.append(f"{label}: {time_text}")
                else:
                    time_parts.append(time_text)

            if time_parts:
                lines.append(f"🕒 <b>Время:</b> {html.escape(', '.join(time_parts))}")

        if city_name:
            lines.append(f"🌆 <b>Город:</b> {html.escape(str(city_name))}")

        if venue_name:
            lines.append(f"📍 <b>Площадка:</b> {html.escape(str(venue_name))}")

        if address:
            lines.append(f"🏠 <b>Адрес:</b> {html.escape(str(address))}")

    if age_limit is not None:
        lines.append(f"🔞 <b>Возраст:</b> {html.escape(str(age_limit))}+")

    if promo_codes:
        lines.append(
            f"🏷 <b>Промокоды:</b> {html.escape(', '.join(map(str, promo_codes)))}"
        )

    if ticket_links:
        first = ticket_links[0]
        url = getattr(first, "url", None)
        if url:
            lines.append(f"🎟 <b>Билеты:</b> {html.escape(str(url))}")

    if chat_links:
        first = chat_links[0]
        url = getattr(first, "url", None)
        if url:
            lines.append(f"💬 <b>Чат:</b> {html.escape(str(url))}")

    if external_links:
        first = external_links[0]
        url = getattr(first, "url", None)
        if url:
            lines.append(f"🔗 <b>Ссылка:</b> {html.escape(str(url))}")

    if description:
        lines.append("")
        lines.append(f"📝 {html.escape(str(description))[:1200]}")

    result = "\n".join(lines).strip()

    if result == "🎫 <b>Афиша</b>":
        return "Не удалось нормально собрать афишу."

    return result


async def start_handler(message: Message) -> None:
    await message.answer(
        "Отправь текст анонса концерта, и я попробую превратить его в афишу."
    )


def create_poster_handler(use_case: ExtractPosterDraftUseCase):
    async def handler(message: Message) -> None:
        poster_input = build_poster_input_from_message(message)

        if poster_input is None:
            await message.answer("Не удалось получить текст из сообщения.")
            return

        try:
            poster_draft = use_case.execute(poster_input)
            result_text = format_poster_draft(poster_draft)
            await message.answer(result_text)
        except Exception as exc:
            await message.answer(
                f"Ошибка при обработке:\n<code>{html.escape(str(exc))}</code>"
            )

    return handler


async def main() -> None:
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    use_case = ExtractPosterDraftUseCase()

    dp.message.register(start_handler, F.text.in_({"/start", "/help"}))
    dp.message.register(create_poster_handler(use_case), F.text | F.caption)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
    
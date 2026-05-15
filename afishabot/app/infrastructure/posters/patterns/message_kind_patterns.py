from __future__ import annotations

import re


PROMO_MESSAGE_RE = re.compile(
    r"\b(?:промокод|promo(?:\s+code)?|код|скидка)\b",
    re.IGNORECASE,
)

GIVEAWAY_MESSAGE_RE = re.compile(
    r"\b(?:розыгрыш|розыгрыши|проходк|победител|репост|реакци)\b",
    re.IGNORECASE,
)

DIGEST_MESSAGE_RE = re.compile(
    r"\b(?:афиша|концерты недели|дайджест|расписание)\b",
    re.IGNORECASE,
)

TOUR_MESSAGE_RE = re.compile(
    r"\b(?:тур|tour)\b",
    re.IGNORECASE,
)

EVENT_MESSAGE_RE = re.compile(
    r"\b(?:концерт|билеты|сегодня|завтра|послезавтра|клуб|арена|площадка)\b",
    re.IGNORECASE,
)

LOW_SIGNAL_MESSAGE_RE = re.compile(
    r"\b(?:лайк|реакци|ждем|ждём|кто|как дела|спасибо)\b",
    re.IGNORECASE,
)


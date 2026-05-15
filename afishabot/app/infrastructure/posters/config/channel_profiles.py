from __future__ import annotations

from app.infrastructure.posters.models.channel_profile import (
    ChannelProfile,
    PosterChannelType,
)


CHANNEL_PROFILES: dict[str, ChannelProfile] = {
    "aurora_concert": ChannelProfile(
        source_name="aurora_concert",
        channel_type=PosterChannelType.VENUE,
        channel_id=1854697448,
        city_name="Санкт-Петербург",
        venue_name="AURORA",
        enabled_hints=("default_city", "default_venue", "venue_channel"),
    ),
    "bosspromotion_ru": ChannelProfile(
        source_name="bosspromotion_ru",
        channel_type=PosterChannelType.PROMO,
        channel_id=1974472172,
        enabled_hints=("promo_channel",),
    ),
    "spbpromocodes": ChannelProfile(
        source_name="spbpromocodes",
        channel_type=PosterChannelType.PROMO,
        city_name="Санкт-Петербург",
        enabled_hints=("promo_channel", "default_city"),
    ),
    "revernpromo": ChannelProfile(
        source_name="revernpromo",
        channel_type=PosterChannelType.PROMO,
        enabled_hints=("promo_channel",),
    ),
    "grompromokod": ChannelProfile(
        source_name="grompromokod",
        channel_type=PosterChannelType.PROMO,
        enabled_hints=("promo_channel",),
    ),
    "concerts_moscow": ChannelProfile(
        source_name="concerts_moscow",
        channel_type=PosterChannelType.CONCERT,
        city_name="Москва",
        enabled_hints=("default_city",),
    ),
    "spb_conc": ChannelProfile(
        source_name="spb_conc",
        channel_type=PosterChannelType.CONCERT,
        city_name="Санкт-Петербург",
        enabled_hints=("default_city",),
    ),
    "conccorp": ChannelProfile(
        source_name="conccorp",
        channel_type=PosterChannelType.MIXED,
    ),
}


def get_channel_profile(source_file: str | None, source_channel_id: int | None) -> ChannelProfile | None:
    if source_file:
        normalized = source_file.replace("\\", "/").split("/")[-1]
        source_name = normalized.removesuffix(".json")
        if source_name in CHANNEL_PROFILES:
            return CHANNEL_PROFILES[source_name]

    if source_channel_id is not None:
        for profile in CHANNEL_PROFILES.values():
            if profile.channel_id == source_channel_id:
                return profile

    return None


CONTENT_ANALYSIS_RULES = [
    "Return only compact valid JSON.",
    "Do not generate images, files, tables or markdown.",
    "Do not explain reasoning.",
    "Input can come from Telegram, website parser, social network, manual import, API, or another source.",
    "Content can be a new event, tour, update, promo, reminder, recap, cancellation, postponement, ticket update, trash or unknown.",
    "Use deep analysis for useful content.",
    "If content is trash, return trash without deep processing.",
    "There may be multiple decisions in one result.",
    "If there are significantly different interpretations, include variants with confidence.",
    "If there is no meaningful difference, return only the most confident variant.",
]

CONTENT_ANALYSIS_TASK = "analyze_incoming_content"

JSON_REPAIR_TASK = "repair_json_response"

JSON_REPAIR_RULES = [
    "Return only compact valid JSON.",
    "Do not explain anything.",
    "Do not add markdown.",
    "Fix the broken AI response so it matches the expected JSON object shape.",
    "Preserve the original meaning as much as possible.",
]


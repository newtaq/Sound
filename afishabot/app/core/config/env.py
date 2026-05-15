import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

ENV_FILE_MAP = {
    "dev": ".env",
    "prod": ".env.prod",
    "test": ".env.test",
}

ENV_FILE = ENV_FILE_MAP.get(ENVIRONMENT, ".env")


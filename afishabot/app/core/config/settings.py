import os 

ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')

ENV_FILE_MAP = {
    "dev": ".env",
    "test": ".env.test",
    "prod": ".env.prod"
}

ENV_FILE = ENV_FILE_MAP.get(ENVIRONMENT, ".env")

os.environ.setdefault("ENV_FILE", ENV_FILE)

from .telegram_api import telegram_api_settings 
from .mtproto import mtproto_settings 
from .database import database_settings

class Settings:
    
    telegram_api = telegram_api_settings
    mtproto = mtproto_settings
    database = database_settings
    
    
settings = Settings()


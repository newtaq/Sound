from pydantic_settings import BaseSettings, SettingsConfigDict

from . import ENV_FILE

class TelegramAPISettings(BaseSettings):
    
    BOT_TOKEN: str = "None" # must be in .env file, but default value is set to avoid errors during development  
    
    model_config = SettingsConfigDict(
        env_file = ENV_FILE,
        env_file_encoding = "utf-8",
        extra = "ignore"
    )

telegram_api_settings = TelegramAPISettings() 


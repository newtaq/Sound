from pydantic_settings import BaseSettings, SettingsConfigDict

from . import ENV_FILE

class MTProtoSettings(BaseSettings):
    
    API_ID: int | None = None  
    API_HASH: str | None = None  
    
    SESSION_NAME: str | None = "afishabot"  # Default session name, can be overridden in .env file
    
    model_config = SettingsConfigDict(
        env_file = ENV_FILE,
        env_file_encoding = "utf-8",
        extra = "ignore"
    )
    
    
mtproto_settings = MTProtoSettings()


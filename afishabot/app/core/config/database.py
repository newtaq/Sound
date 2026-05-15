from tarfile import data_filter
from pydantic_settings import BaseSettings, SettingsConfigDict

from . import ENV_FILE


class DatabaseSettings(BaseSettings):
    
    DB_HOST: str = "localhost"      # Must be set in .env file, but default value is set to avoid errors during development
    DB_PORT: int = 5432             # Must be set in .env file, but default value is set to avoid errors during development
    DB_NAME: str = "afishabot"      # Must be set in .env file, but default value is set to avoid errors during development
    DB_USER: str = "postgres"       # Must be set in .env file, but default value is set to avoid errors during development
    DB_PASSWORD: str | None = None  # Must be set in .env file, but default value is set to avoid errors during development
    
    model_config = SettingsConfigDict(
        env_file = ENV_FILE,
        env_file_encoding = "utf-8",
        extra = "ignore"
    )
    
    
    def build_dsn(self) -> str:
        if self.DB_PASSWORD:
            auth = f"{self.DB_USER}:{self.DB_PASSWORD}"
        else:
            auth = self.DB_USER
            
        return f"postgresql://{auth}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        
    
database_settings = DatabaseSettings()


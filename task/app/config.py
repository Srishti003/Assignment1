from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Transaction Webhook Service"
    APP_ENV: str = "production"
    DEBUG: bool = False
    
    # Database connection string (defaults to local SQLite, or set to PostgreSQL in cloud)
    DATABASE_URL: str = "sqlite:///./transactions.db"
    
    # Background processing simulated delay in seconds (defaults to 30 as required)
    PROCESSING_DELAY_SECONDS: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

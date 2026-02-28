from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # Twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_WHATSAPP_NUMBER: str = "whatsapp:+14155238886"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # App
    APP_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "change-me"
    DEBUG: bool = True

    # Email (optional)
    SENDGRID_API_KEY: Optional[str] = None
    FROM_EMAIL: str = "noreply@uniapply.co.za"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()

settings = get_settings()

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""
    
    # Gemini API
    gemini_api_key: str
    
    # Email Configuration
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str
    smtp_password: str
    email_from: str
    
    # Database
    database_url: str = "sqlite:///./data/reports.db"
    
    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

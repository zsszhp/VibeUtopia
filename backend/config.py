import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.longcat.chat/openai/v1")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "LongCat-Flash-Lite")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/vibeutopia.db")
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 1


settings = Settings()

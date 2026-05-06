import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # 原有配置（向后兼容）
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.longcat.chat/openai/v1")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "LongCat-Flash-Lite")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/vibeutopia.db")
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "1"))

    # 模型路由配置
    MODEL_CONFIG_PATH: str = os.getenv(
        "MODEL_CONFIG_PATH",
        str(Path(__file__).parent / "services" / "model_config.yaml"),
    )
    MODEL_COOLDOWN_SECONDS: int = int(os.getenv("MODEL_COOLDOWN_SECONDS", "300"))
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "")


settings = Settings()

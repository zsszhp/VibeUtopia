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

    # 信号采集配置
    SIGNAL_CONFIG_PATH: str = os.getenv(
        "SIGNAL_CONFIG_PATH",
        str(Path(__file__).parent.parent / "config" / "signal_config.yaml"),
    )
    SIGNAL_DEFAULT_MODE: str = os.getenv("SIGNAL_DEFAULT_MODE", "standard")

    # 知识图谱配置
    GRAPH_CONFIG_PATH: str = os.getenv(
        "GRAPH_CONFIG_PATH",
        str(Path(__file__).parent.parent / "config" / "graph_config.yaml"),
    )
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "vibeutopia2024")

    # MySQL配置（V2.R2新增，优先于SQLite）
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "vibeutopia")

    # 人格工厂配置
    AGENTS_PER_PLATFORM: int = int(os.getenv("AGENTS_PER_PLATFORM", "5"))
    PERSONA_MAX_CONCURRENT: int = int(os.getenv("PERSONA_MAX_CONCURRENT", "5"))
    PERSONA_QUALITY_THRESHOLD: float = float(os.getenv("PERSONA_QUALITY_THRESHOLD", "0.6"))
    AGENT_MEMORY_MAX_PER_AGENT: int = int(os.getenv("AGENT_MEMORY_MAX_PER_AGENT", "100"))
    AGENT_MEMORY_HALF_LIFE_DAYS: int = int(os.getenv("AGENT_MEMORY_HALF_LIFE_DAYS", "7"))


settings = Settings()

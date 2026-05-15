import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # 核心配置
    # 核心配置 (Legacy 模式降级使用)
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QWEN_VL_MODEL: str = os.getenv("QWEN_VL_MODEL", "qwen-vl-plus")

    GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
    GLM_BASE_URL: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    GLM_VL_MODEL: str = os.getenv("GLM_VL_MODEL", "glm-4v-flash")
    
    # 数据库配置
    # 生产环境推荐：mysql+pymysql://user:pass@host:port/db
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/vibeutopia.db")
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./data/chroma")
    
    LLM_TIMEOUT: int = int(os.getenv("LLM_TIMEOUT", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
    MODEL_COOLDOWN_SECONDS: int = int(os.getenv("MODEL_COOLDOWN_SECONDS", "300"))

    # 模型路由配置
    MODEL_CONFIG_PATH: str = os.getenv(
        "MODEL_CONFIG_PATH",
        str(Path(__file__).parent.parent / "config" / "model_config.yaml"),
    )
    DEFAULT_PROVIDER: str = os.getenv("DEFAULT_PROVIDER", "aliyun")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "")
    
    # 硬件检测配置
    HARDWARE_DETECTION_ENABLED: bool = os.getenv("HARDWARE_DETECTION_ENABLED", "true").lower() == "true"
    VRAM_THRESHOLD_LITE: int = int(os.getenv("VRAM_THRESHOLD_LITE", "8"))
    VRAM_THRESHOLD_STANDARD: int = int(os.getenv("VRAM_THRESHOLD_STANDARD", "16"))

    # 知识图谱配置 (Neo4j)
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "vibeutopia2024")

    # MySQL 独立配置 (用于构建 DATABASE_URL)
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "vibe_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "vibe_password")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "vibeutopia")

    # 仿真引擎配置
    AGENTS_PER_PLATFORM: int = int(os.getenv("AGENTS_PER_PLATFORM", "10"))
    MEMORY_RETRIEVAL_LIMIT: int = int(os.getenv("MEMORY_RETRIEVAL_LIMIT", "5"))
    DREAM_CYCLE_INTERVAL: int = int(os.getenv("DREAM_CYCLE_INTERVAL", "3600"))

    # 信号采集配置
    SIGNAL_CONFIG_PATH: str = os.getenv(
        "SIGNAL_CONFIG_PATH",
        str(Path(__file__).parent / "services" / "signal" / "signal_config.yaml"),
    ) # 记忆整合间隔(秒)

    # 多模态风控配置
    KEYFRAME_MAX_FRAMES: int = int(os.getenv("KEYFRAME_MAX_FRAMES", "50"))
    KEYFRAME_INTERVAL_SECONDS: float = float(os.getenv("KEYFRAME_INTERVAL_SECONDS", "5.0"))
    OCR_MIN_CONFIDENCE: float = float(os.getenv("OCR_MIN_CONFIDENCE", "0.5"))
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")


settings = Settings()

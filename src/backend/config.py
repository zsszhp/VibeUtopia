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

    ALIYUN_API_KEY: str = os.getenv("ALIYUN_API_KEY", "")

    GLM_API_KEY: str = os.getenv("GLM_API_KEY", "")
    GLM_BASE_URL: str = os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    GLM_VL_MODEL: str = os.getenv("GLM_VL_MODEL", "glm-4v-flash")

    # V3.2 本地模型部署配置 (Ollama / vLLM)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "ollama")
    VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
    VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "vllm")
    
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
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")

    # MySQL 独立配置 (用于构建 DATABASE_URL)
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "vibe_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
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

    # API 鉴权（可选）：配置后所有 /api/** 与 /ws/** 必须携带 X-API-Key 或 Authorization: Bearer
    # 未配置时本地开发放行；生产环境必须配置，且不得写入仓库
    API_KEY: str = os.getenv("API_KEY", "")

    # API 限流：每客户端每分钟最大请求数（滑动窗口，单进程内存计数）
    # <= 0 表示不限流；覆盖 /api/**（/health 等探活端点除外）
    RATE_LIMIT_PER_MIN: int = int(os.getenv("RATE_LIMIT_PER_MIN", "60"))

    # CORS 配置：逗号分隔的来源白名单，默认仅放行本地开发端口（Vite dev: 3000/5173）
    # 生产环境必须通过 CORS_ALLOW_ORIGINS 显式配置，禁止使用 *
    CORS_ALLOW_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ALLOW_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,"
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:8080,http://127.0.0.1:8080",
        ).split(",")
        if o.strip()
    ]


settings = Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )
    
    # 调试模式
    DEBUG: bool = False
    
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://lemon_user:lemon_password_123@localhost:3306/lemon_kami"
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # JWT 密钥
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENABLE_API_DOCS: bool = False
    
    # 安全配置
    TIMESTAMP_TOLERANCE: int = 60  # 时间戳容忍误差（秒）
    NONCE_TTL: int = 60  # nonce 缓存时间（秒）
    RATE_LIMIT_MAX: int = 100  # 每分钟最大请求次数
    RATE_LIMIT_WINDOW: int = 60  # 限流窗口（秒）
    CORS_ALLOWED_ORIGINS: str = ""  # 逗号分隔的允许跨域来源；生产环境不要使用 *
    
    # 登录加密配置（AES 密钥，Base64 编码）
    LOGIN_AES_KEY: Optional[str] = None  # AES 密钥（Base64 编码的 16-byte 密钥）

    # 首次部署管理员引导密码。生产环境必须显式配置，系统不会内置默认密码。
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None


settings = Settings()

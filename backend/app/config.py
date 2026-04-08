"""Application configuration using Pydantic Settings"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "HSA Tracker"
    app_env: str = "development"
    debug: bool = True
    secret_key: str

    # Database
    database_type: str = "postgresql"
    database_url: str

    # AWS S3
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_s3_bucket: str
    aws_s3_region: str = "us-east-1"

    # JWT Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # WebAuthn (Passkeys)
    webauthn_rp_id: str = "localhost"
    webauthn_rp_name: str = "HSA Tracker"
    webauthn_origin: str = "http://localhost:3001"

    # Registration
    require_invite: bool = False  # When True, new users must supply a valid invite token

    # CORS
    cors_origins: str = "http://localhost:3001"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # Web Push / VAPID (optional — push is silently disabled if not set)
    vapid_private_key: Optional[str] = None  # PEM string
    vapid_public_key: Optional[str] = None   # URL-safe base64
    vapid_claims_email: str = "mailto:admin@localhost"

    # Teller.io bank integration (optional, per-install)
    teller_app_id: Optional[str] = None
    teller_cert_b64: Optional[str] = None          # direct env var (local dev)
    teller_private_key_b64: Optional[str] = None   # direct env var (local dev)
    teller_secret_arn: Optional[str] = None        # Secrets Manager ARN (production)
    teller_env: str = "sandbox"  # "sandbox" or "production"

    # File Upload
    max_upload_size_mb: int = 10
    allowed_mime_types: str = "image/jpeg,image/png,image/heic,application/pdf"

    @property
    def allowed_mime_types_list(self) -> List[str]:
        """Parse allowed MIME types from comma-separated string"""
        return [mime.strip() for mime in self.allowed_mime_types.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        """Convert MB to bytes"""
        return self.max_upload_size_mb * 1024 * 1024


# Global settings instance
settings = Settings()

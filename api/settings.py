# ============================================================
#  NXIO — api/settings.py
#  Pydantic V2 Settings — reads from .env automatically
# ============================================================
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    nxio_api_key:    str   = "changeme"
    nxio_env:        str   = "development"
    db_path:         str   = "data/nxio.db"
    log_level:       str   = "INFO"
    allowed_origin:  str   = "http://localhost:8000"
    paper_capital:   float = 100_000.0
    angel_api_key:   str   = ""
    angel_client_id: str   = ""
    angel_password:  str   = ""


settings = Settings()
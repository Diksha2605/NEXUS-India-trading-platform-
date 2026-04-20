# ============================================================
#  NXIO — api/auth.py
#  API Key Authentication
#  Usage: add dependencies=[Depends(verify_api_key)] to routes
# ============================================================
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from api.settings import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != settings.nxio_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key. Pass X-API-Key header."
        )
    return api_key
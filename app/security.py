from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader

from .config import API_KEY

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="Chave definida em API_KEY")


def verificar_api_key(x_api_key: str | None = Depends(api_key_header)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API ausente ou invalida. Envie o header X-API-Key.",
        )

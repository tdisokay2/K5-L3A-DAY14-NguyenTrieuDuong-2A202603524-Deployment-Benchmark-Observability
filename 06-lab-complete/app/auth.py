"""Require a configured API key without logging it."""
import secrets
from typing import Annotated
from fastapi import Header, HTTPException
from app.config import settings

def verify_api_key(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> str:
    if not settings.agent_api_key or not x_api_key or not secrets.compare_digest(
        x_api_key.encode(), settings.agent_api_key.encode()
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")
    return x_api_key

"""
Authentication middleware for API security
"""
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

# API Key configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key() -> Optional[str]:
    """Get API key from environment variable"""
    return os.getenv("API_KEY")

async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the API key from request headers

    Args:
        api_key: API key from request header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    # Get the expected API key from environment
    expected_api_key = get_api_key()

    # If no API key is configured, allow all requests (not recommended for production)
    if not expected_api_key:
        logger.warning("No API_KEY configured - authentication is disabled!")
        return "disabled"

    # Check if API key was provided in request
    if not api_key:
        logger.warning("Request received without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include 'X-API-Key' header with your request.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Verify API key matches
    if api_key != expected_api_key:
        logger.warning("Invalid API key attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key

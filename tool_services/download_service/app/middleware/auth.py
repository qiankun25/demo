"""API Key authentication middleware."""

from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional

from app.config import settings


api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def verify_api_key(api_key: Optional[str] = None) -> bool:
    """Verify API key if authentication is enabled.
    
    Args:
        api_key: API key from request header
        
    Returns:
        True if authentication is disabled or key is valid
        
    Raises:
        HTTPException: If authentication fails
    """
    # If no API keys configured, allow all requests (development mode)
    if not settings.api_keys_list:
        return True
    
    # If API keys are configured, require valid key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is required",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    if api_key not in settings.api_keys_list:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    
    return True


def get_api_key(request: Request) -> Optional[str]:
    """Extract API key from request header.
    
    Args:
        request: FastAPI request object
        
    Returns:
        API key if present, None otherwise
    """
    return request.headers.get(settings.api_key_header)

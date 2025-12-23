"""Tests for URL validation service."""

import pytest
from app.services.validator import URLValidator


@pytest.mark.asyncio
async def test_validator_valid_url():
    """Test that a valid URL returns True."""
    validator = URLValidator(timeout=10)
    
    # Use a reliable test URL
    is_valid, error = await validator.is_reachable("https://httpbin.org/status/200")
    
    assert is_valid is True
    assert error == ""


@pytest.mark.asyncio
async def test_validator_404_url():
    """Test that a 404 URL returns False with appropriate error."""
    validator = URLValidator(timeout=10)
    
    is_valid, error = await validator.is_reachable("https://httpbin.org/status/404")
    
    assert is_valid is False
    assert "404" in error


@pytest.mark.asyncio
async def test_validator_invalid_domain():
    """Test that an invalid domain returns False with connection error."""
    validator = URLValidator(timeout=5)
    
    is_valid, error = await validator.is_reachable("https://this-domain-does-not-exist-12345.com")
    
    assert is_valid is False
    assert error != ""

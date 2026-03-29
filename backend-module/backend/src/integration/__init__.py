"""
Moodle Client for get student answer with format JSON.
The integration here for system.
"""
from __future__ import annotations


from backend.src.exception import BackendException

import logging


logger = logging.getLogger(__name__)


class IntegrationException(BackendException):
    """Base exception for integration part."""
    _base_code: int = 10000


class AuthenticationException(IntegrationException):
    """Exception raised for authentication errors."""
    _code: int = 1001


class UnSynchronizedSiteInfo(IntegrationException):
    """Exception when API calling without syncornized siteinfo."""
    _code: int = 1002


class APICallingException(IntegrationException):
    """Exception raised for API calling errors."""
    _code: int = 1010

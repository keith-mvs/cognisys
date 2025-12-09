"""
CogniSys Cloud Authentication Module

Provides OAuth 2.0 authentication for cloud providers:
- OneDrive (Microsoft Graph API)
- Google Drive (Google OAuth 2.0)
"""

from .token_storage import TokenStorage, SecureTokenStorage
from .onedrive_auth import OneDriveAuthenticator

__all__ = [
    'TokenStorage',
    'SecureTokenStorage',
    'OneDriveAuthenticator',
]

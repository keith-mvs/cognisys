"""
OneDrive Authentication

Implements OAuth 2.0 authentication for Microsoft Graph API (OneDrive).
Supports:
- Interactive browser-based authentication
- Device code flow (for headless/server environments)
- Token refresh

Requires: msal (Microsoft Authentication Library)
"""

import logging
import webbrowser
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Callable

from .token_storage import TokenStorage, SecureTokenStorage

logger = logging.getLogger(__name__)

# Try to import MSAL
try:
    from msal import PublicClientApplication, SerializableTokenCache
    HAS_MSAL = True
except ImportError:
    HAS_MSAL = False
    logger.warning("msal not installed. OneDrive authentication unavailable.")


# Microsoft Graph API permissions for OneDrive
ONEDRIVE_SCOPES = [
    'Files.Read',           # Read user files
    'Files.ReadWrite',      # Read and write user files
    'Files.Read.All',       # Read all files user can access
    'Files.ReadWrite.All',  # Read and write all files user can access
    'offline_access',       # Get refresh tokens
    'User.Read',            # Read user profile (for account info)
]

# Minimal scopes for read-only access
ONEDRIVE_SCOPES_READONLY = [
    'Files.Read',
    'Files.Read.All',
    'offline_access',
    'User.Read',
]

# Default client ID for public/native apps (you should register your own app)
# This is a placeholder - users should register their own Azure AD app
DEFAULT_CLIENT_ID = None  # Must be set by user


class OneDriveAuthenticator:
    """
    Handles OneDrive authentication via Microsoft Graph API.

    Usage:
        auth = OneDriveAuthenticator(client_id='your-client-id')

        # Interactive authentication (opens browser)
        token = auth.authenticate_interactive()

        # Device code flow (for headless environments)
        token = auth.authenticate_device_code()

        # Get valid token (refreshes if needed)
        access_token = auth.get_access_token()
    """

    AUTHORITY_CONSUMERS = "https://login.microsoftonline.com/consumers"
    AUTHORITY_COMMON = "https://login.microsoftonline.com/common"

    def __init__(
        self,
        client_id: str,
        token_storage: Optional[TokenStorage] = None,
        authority: Optional[str] = None,
        scopes: Optional[list] = None,
        readonly: bool = False,
    ):
        """
        Initialize OneDrive authenticator.

        Args:
            client_id: Azure AD application client ID
            token_storage: Token storage instance (default: SecureTokenStorage)
            authority: Azure AD authority URL (default: consumers for personal accounts)
            scopes: OAuth scopes to request (default: full OneDrive access)
            readonly: If True, request read-only scopes
        """
        if not HAS_MSAL:
            raise ImportError(
                "msal package required for OneDrive authentication. "
                "Install with: pip install msal"
            )

        self.client_id = client_id
        self.token_storage = token_storage or SecureTokenStorage()
        self.authority = authority or self.AUTHORITY_CONSUMERS
        self.scopes = scopes or (ONEDRIVE_SCOPES_READONLY if readonly else ONEDRIVE_SCOPES)

        # Initialize MSAL app with token cache
        self._cache = SerializableTokenCache()
        self._app = PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=self._cache,
        )

        # Try to load existing tokens
        self._load_cache()

    def _load_cache(self):
        """Load token cache from storage."""
        token_data = self.token_storage.load('onedrive')
        if token_data and '_msal_cache' in token_data:
            self._cache.deserialize(token_data['_msal_cache'])
            logger.debug("Loaded MSAL token cache from storage")

    def _save_cache(self):
        """Save token cache to storage."""
        if self._cache.has_state_changed:
            token_data = {
                '_msal_cache': self._cache.serialize(),
                '_updated_at': datetime.now().isoformat(),
            }
            self.token_storage.save('onedrive', token_data)
            logger.debug("Saved MSAL token cache to storage")

    def authenticate_interactive(
        self,
        open_browser: bool = True,
        timeout: int = 120,
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate using interactive browser flow.

        Opens the default browser for user to sign in.

        Args:
            open_browser: Automatically open browser (default: True)
            timeout: Timeout in seconds for authentication

        Returns:
            Token response dict or None if failed
        """
        try:
            logger.info("Starting interactive authentication...")

            # Try to get token silently first (from cache)
            accounts = self._app.get_accounts()
            if accounts:
                result = self._app.acquire_token_silent(
                    scopes=self.scopes,
                    account=accounts[0],
                )
                if result and 'access_token' in result:
                    logger.info("Got token from cache")
                    self._save_cache()
                    return result

            # Need interactive login
            result = self._app.acquire_token_interactive(
                scopes=self.scopes,
                timeout=timeout,
            )

            if result and 'access_token' in result:
                logger.info("Interactive authentication successful")
                self._save_cache()
                return result
            else:
                error = result.get('error_description', result.get('error', 'Unknown error'))
                logger.error(f"Interactive authentication failed: {error}")
                return None

        except Exception as e:
            logger.error(f"Interactive authentication error: {e}")
            return None

    def authenticate_device_code(
        self,
        callback: Optional[Callable[[str, str], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Authenticate using device code flow.

        Useful for headless/server environments where browser is not available.
        User must visit a URL and enter a code to authenticate.

        Args:
            callback: Optional callback(url, code) to handle device code display

        Returns:
            Token response dict or None if failed
        """
        try:
            logger.info("Starting device code authentication...")

            # Initiate device code flow
            flow = self._app.initiate_device_flow(scopes=self.scopes)

            if 'user_code' not in flow:
                error = flow.get('error_description', 'Failed to get device code')
                logger.error(f"Device code flow failed: {error}")
                return None

            # Display instructions
            verification_uri = flow.get('verification_uri', 'https://microsoft.com/devicelogin')
            user_code = flow['user_code']
            message = flow.get('message', f"Go to {verification_uri} and enter code: {user_code}")

            print("\n" + "=" * 60)
            print("DEVICE CODE AUTHENTICATION")
            print("=" * 60)
            print(message)
            print("=" * 60 + "\n")

            if callback:
                callback(verification_uri, user_code)

            # Wait for user to authenticate
            result = self._app.acquire_token_by_device_flow(flow)

            if result and 'access_token' in result:
                logger.info("Device code authentication successful")
                self._save_cache()
                return result
            else:
                error = result.get('error_description', result.get('error', 'Unknown error'))
                logger.error(f"Device code authentication failed: {error}")
                return None

        except Exception as e:
            logger.error(f"Device code authentication error: {e}")
            return None

    def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, refreshing if necessary.

        Returns:
            Access token string or None if not authenticated
        """
        try:
            accounts = self._app.get_accounts()
            if not accounts:
                logger.warning("No accounts found. Need to authenticate first.")
                return None

            # Try silent token acquisition (uses refresh token if needed)
            result = self._app.acquire_token_silent(
                scopes=self.scopes,
                account=accounts[0],
            )

            if result and 'access_token' in result:
                self._save_cache()
                return result['access_token']
            else:
                logger.warning("Failed to get token silently. Re-authentication needed.")
                return None

        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return None

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        """
        Get current account information.

        Returns:
            Account info dict or None
        """
        accounts = self._app.get_accounts()
        if accounts:
            account = accounts[0]
            return {
                'username': account.get('username'),
                'name': account.get('name'),
                'local_account_id': account.get('local_account_id'),
            }
        return None

    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid tokens."""
        return bool(self._app.get_accounts())

    def logout(self) -> bool:
        """
        Log out and clear tokens.

        Returns:
            True if successful
        """
        try:
            # Clear MSAL accounts
            accounts = self._app.get_accounts()
            for account in accounts:
                self._app.remove_account(account)

            # Clear stored tokens
            self.token_storage.delete('onedrive')

            logger.info("Logged out of OneDrive")
            return True

        except Exception as e:
            logger.error(f"Logout error: {e}")
            return False


def create_authenticator(
    client_id: Optional[str] = None,
    readonly: bool = False,
) -> OneDriveAuthenticator:
    """
    Create an OneDrive authenticator with the given or default client ID.

    Args:
        client_id: Azure AD app client ID (required if DEFAULT_CLIENT_ID not set)
        readonly: Request read-only permissions

    Returns:
        OneDriveAuthenticator instance
    """
    if not client_id and not DEFAULT_CLIENT_ID:
        raise ValueError(
            "OneDrive authentication requires an Azure AD client ID. "
            "Register an app at https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade "
            "and provide the client ID."
        )

    return OneDriveAuthenticator(
        client_id=client_id or DEFAULT_CLIENT_ID,
        readonly=readonly,
    )


if __name__ == '__main__':
    # Test authentication (requires valid client ID)
    import sys

    logging.basicConfig(level=logging.DEBUG)

    if not HAS_MSAL:
        print("MSAL not installed. Install with: pip install msal")
        sys.exit(1)

    # You need to provide your own client ID
    # Register an app at https://portal.azure.com
    client_id = os.environ.get('ONEDRIVE_CLIENT_ID')

    if not client_id:
        print("Set ONEDRIVE_CLIENT_ID environment variable to test authentication")
        print("\nTo register an Azure AD app:")
        print("1. Go to https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade")
        print("2. Click 'New registration'")
        print("3. Name: 'CogniSys'")
        print("4. Supported account types: 'Personal Microsoft accounts only'")
        print("5. Redirect URI: 'http://localhost' (Public client/native)")
        print("6. Copy the Application (client) ID")
        sys.exit(1)

    auth = OneDriveAuthenticator(client_id=client_id)

    print("\nChoose authentication method:")
    print("1. Interactive (opens browser)")
    print("2. Device code (for headless)")

    choice = input("\nEnter choice (1 or 2): ").strip()

    if choice == '1':
        result = auth.authenticate_interactive()
    else:
        result = auth.authenticate_device_code()

    if result:
        print("\nAuthentication successful!")
        print(f"Account: {auth.get_account_info()}")
        print(f"Access token (first 50 chars): {result['access_token'][:50]}...")
    else:
        print("\nAuthentication failed")

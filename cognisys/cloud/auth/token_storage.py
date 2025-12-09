"""
Secure Token Storage

Provides secure storage for OAuth tokens using:
1. System keyring (Windows Credential Manager, macOS Keychain, etc.)
2. Encrypted file fallback if keyring unavailable

Tokens are encrypted before storage for additional security.
"""

import json
import os
import logging
import base64
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Try to import optional dependencies
try:
    import keyring
    HAS_KEYRING = True
except ImportError:
    HAS_KEYRING = False
    logger.warning("keyring not installed. Using file-based storage.")

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography not installed. Tokens will be stored unencrypted.")


class TokenStorage(ABC):
    """Abstract base class for token storage."""

    @abstractmethod
    def save(self, provider: str, token_data: Dict[str, Any]) -> bool:
        """
        Save token data for a provider.

        Args:
            provider: Provider identifier (e.g., 'onedrive', 'googledrive')
            token_data: Token data dictionary

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Load token data for a provider.

        Args:
            provider: Provider identifier

        Returns:
            Token data dictionary or None if not found
        """
        pass

    @abstractmethod
    def delete(self, provider: str) -> bool:
        """
        Delete token data for a provider.

        Args:
            provider: Provider identifier

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def exists(self, provider: str) -> bool:
        """Check if token exists for provider."""
        pass


class SecureTokenStorage(TokenStorage):
    """
    Secure token storage using system keyring with encryption.

    Falls back to encrypted file storage if keyring is unavailable.
    """

    APP_NAME = 'cognisys'
    KEY_PREFIX = 'cognisys_oauth_'

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Initialize secure token storage.

        Args:
            storage_dir: Directory for file-based storage (default: ~/.cognisys/tokens)
        """
        self._storage_dir = Path(storage_dir) if storage_dir else Path.home() / '.cognisys' / 'tokens'
        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self._use_keyring = HAS_KEYRING
        self._cipher = self._init_cipher() if HAS_CRYPTO else None

    def _init_cipher(self) -> Optional['Fernet']:
        """Initialize Fernet cipher for encryption."""
        if not HAS_CRYPTO:
            return None

        # Generate or load encryption key
        key_file = self._storage_dir / '.key'

        if key_file.exists():
            with open(key_file, 'rb') as f:
                key = f.read()
        else:
            # Generate new key
            key = Fernet.generate_key()
            # Save key with restricted permissions
            key_file.touch(mode=0o600)
            with open(key_file, 'wb') as f:
                f.write(key)

        return Fernet(key)

    def _encrypt(self, data: str) -> str:
        """Encrypt data string."""
        if self._cipher:
            encrypted = self._cipher.encrypt(data.encode('utf-8'))
            return base64.b64encode(encrypted).decode('utf-8')
        return data

    def _decrypt(self, data: str) -> str:
        """Decrypt data string."""
        if self._cipher:
            encrypted = base64.b64decode(data.encode('utf-8'))
            decrypted = self._cipher.decrypt(encrypted)
            return decrypted.decode('utf-8')
        return data

    def save(self, provider: str, token_data: Dict[str, Any]) -> bool:
        """Save token data securely."""
        try:
            # Add metadata
            token_data['_stored_at'] = datetime.now().isoformat()
            token_data['_provider'] = provider

            # Serialize and encrypt
            json_data = json.dumps(token_data)
            encrypted_data = self._encrypt(json_data)

            if self._use_keyring:
                # Store in system keyring
                key_name = f"{self.KEY_PREFIX}{provider}"
                keyring.set_password(self.APP_NAME, key_name, encrypted_data)
                logger.debug(f"Saved token for {provider} to keyring")
            else:
                # Fall back to file storage
                token_file = self._storage_dir / f"{provider}.token"
                token_file.touch(mode=0o600)
                with open(token_file, 'w') as f:
                    f.write(encrypted_data)
                logger.debug(f"Saved token for {provider} to file")

            return True

        except Exception as e:
            logger.error(f"Failed to save token for {provider}: {e}")
            return False

    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        """Load token data."""
        try:
            encrypted_data = None

            if self._use_keyring:
                key_name = f"{self.KEY_PREFIX}{provider}"
                encrypted_data = keyring.get_password(self.APP_NAME, key_name)

            if not encrypted_data:
                # Try file storage
                token_file = self._storage_dir / f"{provider}.token"
                if token_file.exists():
                    with open(token_file, 'r') as f:
                        encrypted_data = f.read()

            if not encrypted_data:
                return None

            # Decrypt and deserialize
            json_data = self._decrypt(encrypted_data)
            return json.loads(json_data)

        except Exception as e:
            logger.error(f"Failed to load token for {provider}: {e}")
            return None

    def delete(self, provider: str) -> bool:
        """Delete token data."""
        try:
            deleted = False

            if self._use_keyring:
                key_name = f"{self.KEY_PREFIX}{provider}"
                try:
                    keyring.delete_password(self.APP_NAME, key_name)
                    deleted = True
                except keyring.errors.PasswordDeleteError:
                    pass

            # Also delete file if exists
            token_file = self._storage_dir / f"{provider}.token"
            if token_file.exists():
                token_file.unlink()
                deleted = True

            return deleted

        except Exception as e:
            logger.error(f"Failed to delete token for {provider}: {e}")
            return False

    def exists(self, provider: str) -> bool:
        """Check if token exists."""
        if self._use_keyring:
            key_name = f"{self.KEY_PREFIX}{provider}"
            if keyring.get_password(self.APP_NAME, key_name):
                return True

        token_file = self._storage_dir / f"{provider}.token"
        return token_file.exists()

    def list_providers(self) -> list:
        """List all providers with stored tokens."""
        providers = set()

        # Check file storage
        for token_file in self._storage_dir.glob('*.token'):
            providers.add(token_file.stem)

        return list(providers)


class MemoryTokenStorage(TokenStorage):
    """In-memory token storage for testing."""

    def __init__(self):
        self._tokens: Dict[str, Dict[str, Any]] = {}

    def save(self, provider: str, token_data: Dict[str, Any]) -> bool:
        self._tokens[provider] = token_data
        return True

    def load(self, provider: str) -> Optional[Dict[str, Any]]:
        return self._tokens.get(provider)

    def delete(self, provider: str) -> bool:
        if provider in self._tokens:
            del self._tokens[provider]
            return True
        return False

    def exists(self, provider: str) -> bool:
        return provider in self._tokens


if __name__ == '__main__':
    # Test token storage
    logging.basicConfig(level=logging.DEBUG)

    storage = SecureTokenStorage()

    # Test save
    test_token = {
        'access_token': 'test_access_token_12345',
        'refresh_token': 'test_refresh_token_67890',
        'expires_in': 3600,
    }

    print("Testing token storage...")
    print(f"  Keyring available: {HAS_KEYRING}")
    print(f"  Encryption available: {HAS_CRYPTO}")

    if storage.save('test_provider', test_token):
        print("  Save: OK")
    else:
        print("  Save: FAILED")

    # Test load
    loaded = storage.load('test_provider')
    if loaded and loaded.get('access_token') == 'test_access_token_12345':
        print("  Load: OK")
    else:
        print("  Load: FAILED")

    # Test exists
    if storage.exists('test_provider'):
        print("  Exists: OK")
    else:
        print("  Exists: FAILED")

    # Test delete
    if storage.delete('test_provider'):
        print("  Delete: OK")
    else:
        print("  Delete: FAILED")

    # Verify deletion
    if not storage.exists('test_provider'):
        print("  Verify delete: OK")
    else:
        print("  Verify delete: FAILED")

"""
Cloud Commands

CLI commands for cloud storage integration:
- cloud detect: Find mounted cloud folders
- cloud auth: Authenticate with cloud providers
- cloud status: Show cloud connection status
- cloud sync: Sync files with cloud storage
"""

import click
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from cognisys.cloud.detection import CloudFolderDetector

logger = logging.getLogger(__name__)


def get_db_path() -> str:
    """Get default database path."""
    db_dir = Path.home() / '.cognisys'
    db_dir.mkdir(parents=True, exist_ok=True)
    return str(db_dir / 'file_registry.db')


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(db_path or get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


@click.group()
def cloud():
    """Cloud storage integration commands."""
    pass


@cloud.command('detect')
@click.option('--add', is_flag=True, help='Add detected folders as sources')
def detect(add: bool):
    """Detect mounted cloud storage folders."""
    detector = CloudFolderDetector()
    folders = detector.detect_all()

    if not folders:
        click.echo("No cloud storage folders detected.")
        click.echo("\nSupported providers:")
        click.echo("  - OneDrive (sync client required)")
        click.echo("  - Google Drive (Drive for Desktop required)")
        click.echo("  - iCloud (iCloud for Windows required)")
        click.echo("  - Proton Drive (Proton Drive app required)")
        return

    click.echo(f"Found {len(folders)} cloud storage folder(s):\n")

    for folder in folders:
        click.echo(f"  {folder.provider.upper()}")
        click.echo(f"    Path: {folder.local_path}")
        click.echo(f"    On-Demand: {'Yes' if folder.on_demand_enabled else 'No'}")
        click.echo(f"    Sync State: {folder.sync_state or 'Unknown'}")
        click.echo()

    if add:
        import uuid
        conn = get_connection()
        cursor = conn.cursor()
        added = 0
        for folder in folders:
            source_name = f"{folder.provider}_mounted"
            # Check if already exists
            cursor.execute(
                "SELECT source_id FROM sources WHERE source_name = ?",
                (source_name,)
            )
            existing = cursor.fetchone()

            if existing:
                click.echo(f"Source '{source_name}' already exists, skipping.")
                continue

            # Add as source
            source_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO sources (
                    source_id, source_name, source_type, provider, path,
                    scan_mode, priority, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source_id,
                source_name,
                'cloud_mounted',
                folder.provider,
                str(folder.local_path),
                'manual',
                80,
                True,
            ))
            conn.commit()
            click.echo(f"Added source: {source_name}")
            added += 1
        conn.close()

        if added:
            click.echo(f"\nAdded {added} source(s). Use 'cognisys source list' to view.")


@cloud.command('auth')
@click.option('--provider', '-p', required=True,
              type=click.Choice(['onedrive', 'googledrive']),
              help='Cloud provider to authenticate')
@click.option('--client-id', envvar='ONEDRIVE_CLIENT_ID',
              help='OAuth client ID (or set ONEDRIVE_CLIENT_ID env var)')
@click.option('--device-code', is_flag=True,
              help='Use device code flow (for headless environments)')
@click.option('--readonly', is_flag=True,
              help='Request read-only permissions')
def auth(provider: str, client_id: Optional[str], device_code: bool, readonly: bool):
    """Authenticate with a cloud provider."""
    if provider == 'onedrive':
        _auth_onedrive(client_id, device_code, readonly)
    elif provider == 'googledrive':
        click.echo("Google Drive authentication not yet implemented.")
        click.echo("Use mounted Google Drive folder instead (cognisys cloud detect)")
    else:
        click.echo(f"Unknown provider: {provider}")


def _auth_onedrive(client_id: Optional[str], device_code: bool, readonly: bool):
    """Authenticate with OneDrive."""
    if not client_id:
        click.echo("OneDrive authentication requires an Azure AD client ID.")
        click.echo("\nTo register an Azure AD application:")
        click.echo("  1. Go to https://portal.azure.com")
        click.echo("  2. Navigate to Azure Active Directory > App registrations")
        click.echo("  3. Click 'New registration'")
        click.echo("  4. Name: 'CogniSys' (or your preferred name)")
        click.echo("  5. Supported account types: 'Personal Microsoft accounts only'")
        click.echo("  6. Redirect URI: Select 'Public client/native', enter 'http://localhost'")
        click.echo("  7. Click Register")
        click.echo("  8. Copy the 'Application (client) ID'")
        click.echo("\nThen run:")
        click.echo("  cognisys cloud auth --provider onedrive --client-id <your-client-id>")
        click.echo("\nOr set the environment variable:")
        click.echo("  $env:ONEDRIVE_CLIENT_ID = '<your-client-id>'  # PowerShell")
        return

    try:
        from cognisys.cloud.auth.onedrive_auth import OneDriveAuthenticator
    except ImportError as e:
        click.echo(f"Missing dependency: {e}")
        click.echo("\nInstall required packages:")
        click.echo("  pip install msal keyring cryptography")
        return

    try:
        auth = OneDriveAuthenticator(client_id=client_id, readonly=readonly)

        if auth.is_authenticated():
            account = auth.get_account_info()
            click.echo(f"Already authenticated as: {account.get('username', 'Unknown')}")
            if not click.confirm("Re-authenticate?"):
                return

        click.echo("\nStarting OneDrive authentication...")

        if device_code:
            click.echo("Using device code flow (for headless environments).\n")
            result = auth.authenticate_device_code()
        else:
            click.echo("Opening browser for authentication...")
            click.echo("(If browser doesn't open, use --device-code flag)\n")
            result = auth.authenticate_interactive()

        if result and 'access_token' in result:
            account = auth.get_account_info()
            click.echo("\nAuthentication successful!")
            click.echo(f"  Account: {account.get('username', 'Unknown')}")
            click.echo(f"  Scopes: {'Read-only' if readonly else 'Full access'}")
            click.echo("\nYou can now add OneDrive API sources:")
            click.echo("  cognisys source add onedrive_api --type cloud_api --provider onedrive --path /Documents")

            # Store provider info in database
            _store_provider_info('onedrive', client_id, account)

        else:
            click.echo("\nAuthentication failed.")
            if result:
                error = result.get('error_description', result.get('error', 'Unknown error'))
                click.echo(f"Error: {error}")

    except Exception as e:
        click.echo(f"\nAuthentication error: {e}")
        logger.exception("OneDrive authentication failed")


def _store_provider_info(provider: str, client_id: str, account: dict):
    """Store provider info in database."""
    try:
        from datetime import datetime
        import uuid

        conn = get_connection()
        cursor = conn.cursor()

        # Check if provider already exists
        cursor.execute(
            "SELECT provider_id FROM cloud_providers WHERE provider_type = ?",
            (provider,)
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing
            cursor.execute("""
                UPDATE cloud_providers
                SET account_name = ?, account_email = ?, last_auth_at = ?, is_active = ?
                WHERE provider_id = ?
            """, (
                account.get('name'),
                account.get('username'),
                datetime.now().isoformat(),
                True,
                existing['provider_id'],
            ))
        else:
            # Insert new
            cursor.execute("""
                INSERT INTO cloud_providers (
                    provider_id, provider_type, account_name, account_email,
                    last_auth_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                provider,
                account.get('name'),
                account.get('username'),
                datetime.now().isoformat(),
                True,
            ))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.warning(f"Failed to store provider info: {e}")


@cloud.command('status')
def status():
    """Show cloud connection status."""
    click.echo("Cloud Provider Status\n")

    # Check database for providers
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT provider_type, account_name, account_email, last_auth_at, is_active
            FROM cloud_providers
            ORDER BY provider_type
        """)
        providers = cursor.fetchall()
        conn.close()

        if providers:
            click.echo("Authenticated Providers:")
            for p in providers:
                status_icon = "[+]" if p['is_active'] else "[-]"
                click.echo(f"  {status_icon} {p['provider_type'].upper()}")
                click.echo(f"      Account: {p['account_email'] or p['account_name'] or 'Unknown'}")
                click.echo(f"      Last Auth: {p['last_auth_at'] or 'Unknown'}")
                click.echo()
        else:
            click.echo("No authenticated cloud providers.")
            click.echo("\nTo authenticate:")
            click.echo("  cognisys cloud auth --provider onedrive --client-id <client-id>")

    except Exception as e:
        logger.warning(f"Database error: {e}")
        click.echo("Unable to check provider status (database not initialized?)")

    # Check for mounted folders
    click.echo("\nMounted Cloud Folders:")
    detector = CloudFolderDetector()
    folders = detector.detect_all()

    if folders:
        for folder in folders:
            status_icon = "[M]"  # Mounted
            click.echo(f"  {status_icon} {folder.provider.upper()}: {folder.local_path}")
    else:
        click.echo("  No mounted cloud folders detected.")


@cloud.command('sync')
@click.argument('source_name')
@click.option('--direction', '-d',
              type=click.Choice(['pull', 'push', 'bidirectional']),
              default='pull',
              help='Sync direction')
@click.option('--remote-path', '-r', default='',
              help='Remote path to sync')
@click.option('--local-path', '-l',
              help='Local path for sync (default: staging directory)')
@click.option('--dry-run', is_flag=True,
              help='Show what would be synced without making changes')
def sync(source_name: str, direction: str, remote_path: str,
         local_path: Optional[str], dry_run: bool):
    """Sync files with a cloud source."""
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Get source configuration
        cursor.execute("""
            SELECT * FROM sources
            WHERE source_name = ? AND source_type = 'cloud_api'
        """, (source_name,))
        source = cursor.fetchone()

        if not source:
            conn.close()
            click.echo(f"Source '{source_name}' not found or is not a cloud API source.")
            click.echo("\nUse 'cognisys source list' to see available sources.")
            click.echo("Use 'cognisys source add' to add a cloud API source.")
            return

        # Get provider credentials
        cursor.execute("""
            SELECT * FROM cloud_providers
            WHERE provider_type = ? AND is_active = 1
        """, (source['provider'],))
        provider = cursor.fetchone()
        conn.close()

        if not provider:
            click.echo(f"No authenticated {source['provider']} provider found.")
            click.echo(f"\nRun: cognisys cloud auth --provider {source['provider']}")
            return

        # Create sync manager
        from cognisys.cloud.sync import SyncManager, SyncConfig, SyncDirection

        # Determine local path
        if not local_path:
            local_path = str(Path.home() / '.cognisys' / 'staging' / source_name)
            Path(local_path).mkdir(parents=True, exist_ok=True)

        # For now, just show what we would do
        click.echo(f"Sync: {source_name}")
        click.echo(f"  Provider: {source['provider']}")
        click.echo(f"  Direction: {direction}")
        click.echo(f"  Remote path: {remote_path or '/'}")
        click.echo(f"  Local path: {local_path}")
        click.echo(f"  Dry run: {dry_run}")

        if source['provider'] == 'onedrive':
            # Create OneDrive source
            try:
                import os
                from cognisys.storage.onedrive import OneDriveSource
                from cognisys.storage.local import LocalFileSource

                client_id = os.environ.get('ONEDRIVE_CLIENT_ID')
                if not client_id:
                    click.echo("\nError: ONEDRIVE_CLIENT_ID environment variable not set.")
                    return

                click.echo("\nInitializing OneDrive connection...")
                onedrive = OneDriveSource(client_id=client_id, root_path=source['path'])

                if not onedrive.connect():
                    click.echo("Failed to connect to OneDrive. Please re-authenticate.")
                    click.echo("  cognisys cloud auth --provider onedrive --client-id <id>")
                    return

                local = LocalFileSource(local_path)

                config = SyncConfig(
                    direction=SyncDirection(direction),
                    dry_run=dry_run,
                )

                manager = SyncManager(onedrive, local, config)

                click.echo("Starting sync...")
                if direction == 'pull':
                    stats = manager.pull(remote_path, local_path)
                elif direction == 'push':
                    stats = manager.push(local_path, remote_path)
                else:
                    stats = manager.sync(remote_path, local_path)

                click.echo(f"\nSync complete!")
                click.echo(f"  Files scanned: {stats.files_scanned}")
                click.echo(f"  Downloaded: {stats.files_downloaded}")
                click.echo(f"  Uploaded: {stats.files_uploaded}")
                click.echo(f"  Skipped: {stats.files_skipped}")
                click.echo(f"  Conflicts: {stats.files_conflicted}")
                click.echo(f"  Errors: {len(stats.errors)}")

                if stats.errors:
                    click.echo("\nErrors:")
                    for error in stats.errors[:5]:  # Show first 5
                        click.echo(f"  - {error}")
                    if len(stats.errors) > 5:
                        click.echo(f"  ... and {len(stats.errors) - 5} more")

            except ImportError as e:
                click.echo(f"\nMissing dependency: {e}")
                click.echo("Install required packages:")
                click.echo("  pip install msal keyring cryptography")

        else:
            click.echo(f"\nSync not yet implemented for {source['provider']}")

    except Exception as e:
        click.echo(f"\nSync error: {e}")
        logger.exception("Sync failed")


@cloud.command('logout')
@click.option('--provider', '-p',
              type=click.Choice(['onedrive', 'googledrive', 'all']),
              default='all',
              help='Provider to log out from')
def logout(provider: str):
    """Log out from cloud providers."""
    providers_to_logout = ['onedrive', 'googledrive'] if provider == 'all' else [provider]

    for p in providers_to_logout:
        if p == 'onedrive':
            try:
                from cognisys.cloud.auth.onedrive_auth import OneDriveAuthenticator
                import os

                client_id = os.environ.get('ONEDRIVE_CLIENT_ID')
                if client_id:
                    auth = OneDriveAuthenticator(client_id=client_id)
                    if auth.is_authenticated():
                        auth.logout()
                        click.echo(f"Logged out from OneDrive")
                    else:
                        click.echo("Not logged into OneDrive")
                else:
                    click.echo("OneDrive: No client ID configured")

            except ImportError:
                click.echo("OneDrive auth module not available")

        elif p == 'googledrive':
            click.echo("Google Drive logout not yet implemented")

    # Update database
    try:
        conn = get_connection()
        cursor = conn.cursor()
        if provider == 'all':
            cursor.execute("UPDATE cloud_providers SET is_active = 0")
        else:
            cursor.execute(
                "UPDATE cloud_providers SET is_active = 0 WHERE provider_type = ?",
                (provider,)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Database update failed: {e}")

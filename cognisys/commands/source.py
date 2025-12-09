"""
CLI Commands for Source Management

Provides commands to manage the source library:
- List configured sources
- Add new sources (local, network, cloud)
- Remove sources
- Enable/disable sources
- Show source status
"""

import click
import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..cloud.detection import CloudFolderDetector, CloudFolder
from ..storage.local import LocalFileSource


def get_db_path() -> str:
    """Get the default database path."""
    return '.cognisys/file_registry.db'


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(db_path or get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


@click.group()
def source():
    """Manage file sources (local, network, cloud)."""
    pass


@source.command('list')
@click.option('--db', default=None, help='Database path')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table')
def list_sources(db: Optional[str], output_format: str):
    """List all configured sources."""
    conn = get_connection(db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT source_id, source_name, source_type, provider, path,
               scan_mode, priority, is_active, last_scan_at, last_scan_files
        FROM sources
        ORDER BY priority DESC, source_name
    """)

    sources = cursor.fetchall()
    conn.close()

    if not sources:
        click.echo("[INFO] No sources configured. Use 'cognisys source add' to add sources.")
        click.echo("[TIP] Run 'cognisys source detect' to auto-detect cloud folders.")
        return

    if output_format == 'json':
        import json
        data = [dict(row) for row in sources]
        click.echo(json.dumps(data, indent=2, default=str))
    else:
        click.echo(f"\n{'Source Name':<25} {'Type':<15} {'Path':<40} {'Active':<8} {'Last Scan':<20}")
        click.echo("=" * 110)

        for row in sources:
            active = 'Yes' if row['is_active'] else 'No'
            last_scan = row['last_scan_at'][:16] if row['last_scan_at'] else 'Never'
            path_display = str(row['path'])[:38] + '..' if len(str(row['path'])) > 40 else row['path']

            click.echo(
                f"{row['source_name']:<25} "
                f"{row['source_type']:<15} "
                f"{path_display:<40} "
                f"{active:<8} "
                f"{last_scan:<20}"
            )

        click.echo(f"\nTotal: {len(sources)} source(s)")


@source.command('add')
@click.argument('name')
@click.option('--type', 'source_type', required=True,
              type=click.Choice(['local', 'network', 'cloud_mounted', 'cloud_api']),
              help='Source type')
@click.option('--path', required=True, help='Source path (local, network, or cloud)')
@click.option('--provider', type=click.Choice(['onedrive', 'googledrive', 'icloud', 'proton']),
              help='Cloud provider (for cloud sources)')
@click.option('--scan-mode', default='manual',
              type=click.Choice(['watch', 'scheduled', 'manual']),
              help='Scan mode')
@click.option('--schedule', help='Cron schedule (for scheduled mode)')
@click.option('--priority', default=50, type=int, help='Priority (0-100, higher=preferred)')
@click.option('--db', default=None, help='Database path')
def add_source(name: str, source_type: str, path: str, provider: Optional[str],
               scan_mode: str, schedule: Optional[str], priority: int, db: Optional[str]):
    """Add a new source to the library."""

    # Validate path for local sources
    if source_type in ('local', 'cloud_mounted'):
        path_obj = Path(path)
        if not path_obj.exists():
            click.echo(f"[ERROR] Path does not exist: {path}", err=True)
            raise click.Abort()
        if not path_obj.is_dir():
            click.echo(f"[ERROR] Path is not a directory: {path}", err=True)
            raise click.Abort()

    # Validate provider for cloud sources
    if source_type in ('cloud_mounted', 'cloud_api') and not provider:
        click.echo("[ERROR] Cloud sources require --provider", err=True)
        raise click.Abort()

    # Validate schedule for scheduled mode
    if scan_mode == 'scheduled' and not schedule:
        click.echo("[ERROR] Scheduled mode requires --schedule (cron expression)", err=True)
        raise click.Abort()

    conn = get_connection(db)
    cursor = conn.cursor()

    # Check if name already exists
    cursor.execute("SELECT 1 FROM sources WHERE source_name = ?", (name,))
    if cursor.fetchone():
        click.echo(f"[ERROR] Source '{name}' already exists", err=True)
        conn.close()
        raise click.Abort()

    # Insert source
    source_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO sources (
            source_id, source_name, source_type, provider, path,
            scan_mode, schedule, priority, is_active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (source_id, name, source_type, provider, path, scan_mode, schedule, priority, now))

    conn.commit()
    conn.close()

    click.echo(f"[SUCCESS] Added source: {name}")
    click.echo(f"  ID: {source_id}")
    click.echo(f"  Type: {source_type}")
    click.echo(f"  Path: {path}")
    if provider:
        click.echo(f"  Provider: {provider}")
    click.echo(f"  Scan Mode: {scan_mode}")
    click.echo(f"  Priority: {priority}")


@source.command('remove')
@click.argument('name')
@click.option('--db', default=None, help='Database path')
@click.option('--force', is_flag=True, help='Skip confirmation')
def remove_source(name: str, db: Optional[str], force: bool):
    """Remove a source from the library."""
    conn = get_connection(db)
    cursor = conn.cursor()

    # Check if source exists
    cursor.execute("SELECT source_id, path FROM sources WHERE source_name = ?", (name,))
    row = cursor.fetchone()

    if not row:
        click.echo(f"[ERROR] Source '{name}' not found", err=True)
        conn.close()
        raise click.Abort()

    if not force:
        if not click.confirm(f"Remove source '{name}' ({row['path']})?"):
            click.echo("Cancelled.")
            conn.close()
            return

    cursor.execute("DELETE FROM sources WHERE source_name = ?", (name,))
    conn.commit()
    conn.close()

    click.echo(f"[SUCCESS] Removed source: {name}")


@source.command('enable')
@click.argument('name')
@click.option('--db', default=None, help='Database path')
def enable_source(name: str, db: Optional[str]):
    """Enable a source."""
    conn = get_connection(db)
    cursor = conn.cursor()

    cursor.execute("UPDATE sources SET is_active = 1 WHERE source_name = ?", (name,))

    if cursor.rowcount == 0:
        click.echo(f"[ERROR] Source '{name}' not found", err=True)
        conn.close()
        raise click.Abort()

    conn.commit()
    conn.close()
    click.echo(f"[SUCCESS] Enabled source: {name}")


@source.command('disable')
@click.argument('name')
@click.option('--db', default=None, help='Database path')
def disable_source(name: str, db: Optional[str]):
    """Disable a source."""
    conn = get_connection(db)
    cursor = conn.cursor()

    cursor.execute("UPDATE sources SET is_active = 0 WHERE source_name = ?", (name,))

    if cursor.rowcount == 0:
        click.echo(f"[ERROR] Source '{name}' not found", err=True)
        conn.close()
        raise click.Abort()

    conn.commit()
    conn.close()
    click.echo(f"[SUCCESS] Disabled source: {name}")


@source.command('status')
@click.option('--db', default=None, help='Database path')
def source_status(db: Optional[str]):
    """Show detailed status of all sources."""
    conn = get_connection(db)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*,
               (SELECT COUNT(*) FROM file_registry WHERE source_id = s.source_id) as file_count
        FROM sources s
        ORDER BY s.priority DESC
    """)

    sources = cursor.fetchall()
    conn.close()

    if not sources:
        click.echo("[INFO] No sources configured.")
        return

    click.echo("\n" + "=" * 80)
    click.echo("SOURCE STATUS")
    click.echo("=" * 80)

    for row in sources:
        status_icon = '+' if row['is_active'] else '-'
        click.echo(f"\n[{status_icon}] {row['source_name']}")
        click.echo(f"    Type: {row['source_type']}")
        click.echo(f"    Path: {row['path']}")
        if row['provider']:
            click.echo(f"    Provider: {row['provider']}")
        click.echo(f"    Scan Mode: {row['scan_mode']}")
        click.echo(f"    Priority: {row['priority']}")
        click.echo(f"    Files Tracked: {row['file_count'] or 0:,}")
        if row['last_scan_at']:
            click.echo(f"    Last Scan: {row['last_scan_at'][:19]}")
            if row['last_scan_files'] is not None:
                click.echo(f"    Last Scan Files: {row['last_scan_files']:,}")

    click.echo("\n" + "=" * 80)


@source.command('detect')
@click.option('--add', 'auto_add', is_flag=True, help='Automatically add detected sources')
@click.option('--db', default=None, help='Database path')
def detect_sources(auto_add: bool, db: Optional[str]):
    """Auto-detect cloud storage folders."""
    detector = CloudFolderDetector()
    folders = detector.detect_all()

    if not folders:
        click.echo("[INFO] No cloud folders detected.")
        return

    click.echo(f"\nDetected {len(folders)} cloud folder(s):\n")

    conn = get_connection(db) if auto_add else None

    for i, folder in enumerate(folders, 1):
        status = 'EXISTS' if folder.exists else 'NOT FOUND'
        on_demand = ' (On-Demand)' if folder.on_demand_enabled else ''

        click.echo(f"  [{i}] {folder.provider.upper()}{on_demand}")
        click.echo(f"      Path: {folder.local_path}")
        click.echo(f"      Status: {status}")
        if folder.account_email:
            click.echo(f"      Account: {folder.account_email}")

        if auto_add and folder.exists and conn:
            # Generate source name
            source_name = f"{folder.provider}_auto"
            cursor = conn.cursor()

            # Check if already exists
            cursor.execute("SELECT 1 FROM sources WHERE path = ?", (str(folder.local_path),))
            if not cursor.fetchone():
                source_id = str(uuid.uuid4())
                now = datetime.now().isoformat()

                cursor.execute("""
                    INSERT INTO sources (
                        source_id, source_name, source_type, provider, path,
                        scan_mode, priority, is_active, created_at
                    ) VALUES (?, ?, 'cloud_mounted', ?, ?, 'manual', 70, 1, ?)
                """, (source_id, source_name, folder.provider, str(folder.local_path), now))

                click.echo(f"      -> Added as '{source_name}'")
            else:
                click.echo(f"      -> Already configured")

        click.echo()

    if conn:
        conn.commit()
        conn.close()


# Import cloud command from dedicated module
from .cloud import cloud

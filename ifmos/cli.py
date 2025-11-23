"""
Command-line interface for IFMOS.
Provides user-friendly commands for all system operations.
"""

import click
import yaml
from pathlib import Path

from .models.database import Database
from .core.scanner import FileScanner
from .core.analyzer import Analyzer
from .core.reporter import Reporter
from .core.structure_generator import StructureProposalGenerator
from .core.migrator import MigrationPlanner, MigrationExecutor
from .utils.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


@click.group()
@click.option('--config', default='ifmos/config/default_config.yml', help='Configuration file path')
@click.option('--log-level', default='INFO', help='Logging level')
@click.pass_context
def cli(ctx, config, log_level):
    """IFMOS - Intelligent File Management and Organization System"""
    setup_logging(level=log_level)

    # Load configuration
    config_path = Path(config)
    if config_path.exists():
        with open(config_path) as f:
            ctx.obj = yaml.safe_load(f)
    else:
        ctx.obj = {}
        logger.warning(f"Config file not found: {config}. Using defaults.")


@cli.command()
@click.option('--roots', '-r', multiple=True, required=True, help='Root directories to scan')
@click.option('--config', default='ifmos/config/scan_config.yml', help='Scan configuration file')
@click.option('--db', default='db/ifmos.db', help='Database path')
@click.option('--session-id', help='Optional custom session ID')
@click.pass_context
def scan(ctx, roots, config, db, session_id):
    """Scan file systems and build index."""
    click.echo(f"[INFO] Starting scan of {len(roots)} root path(s)")

    # Load scan config
    config_path = Path(config)
    if config_path.exists():
        with open(config_path) as f:
            scan_config = yaml.safe_load(f)
    else:
        scan_config = ctx.obj

    # Initialize database and scanner
    database = Database(db)
    scanner = FileScanner(database, scan_config)

    # Perform scan
    try:
        result_session_id = scanner.scan_roots(list(roots))

        stats = scanner.get_stats()

        click.echo(f"[SUCCESS] Scan completed!")
        click.echo(f"  Session ID: {result_session_id}")
        click.echo(f"  Files scanned: {stats['files_scanned']:,}")
        click.echo(f"  Folders scanned: {stats['folders_scanned']:,}")
        click.echo(f"  Total size: {stats['total_size'] / 1e9:.2f} GB")
        click.echo(f"  Errors: {stats['errors']}")
        click.echo(f"\nDatabase: {db}")

    except Exception as e:
        click.echo(f"[ERROR] Scan failed: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--session', required=True, help='Session ID to analyze')
@click.option('--rules', default='ifmos/config/analysis_rules.yml', help='Analysis rules file')
@click.option('--db', default='db/ifmos.db', help='Database path')
@click.pass_context
def analyze(ctx, session, rules, db):
    """Analyze scanned files and detect duplicates."""
    click.echo(f"[INFO] Analyzing session: {session}")

    # Load rules
    rules_path = Path(rules)
    if rules_path.exists():
        with open(rules_path) as f:
            rules_config = yaml.safe_load(f)
    else:
        rules_config = ctx.obj

    # Initialize database and analyzer
    database = Database(db)
    analyzer = Analyzer(database, rules_config)

    # Run analysis
    try:
        stats = analyzer.analyze_session(session)

        click.echo(f"[SUCCESS] Analysis complete!")
        click.echo(f"  Duplicate groups: {stats['duplicate_groups']:,}")
        click.echo(f"  Duplicate files: {stats['duplicate_files']:,}")
        click.echo(f"  Wasted space: {stats['space_wasted'] / 1e9:.2f} GB")

    except Exception as e:
        click.echo(f"[ERROR] Analysis failed: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--session', required=True, help='Session ID to report on')
@click.option('--output', '-o', default='reports', help='Output directory')
@click.option('--format', '-f', multiple=True, default=['html', 'json'], help='Output formats')
@click.option('--db', default='db/ifmos.db', help='Database path')
@click.pass_context
def report(ctx, session, output, format, db):
    """Generate analysis reports."""
    click.echo(f"[INFO] Generating reports for session: {session}")

    # Initialize database and reporter
    database = Database(db)
    reporter = Reporter(database, ctx.obj)

    # Generate reports
    try:
        reporter.generate_report(session, output, list(format))

        click.echo(f"[SUCCESS] Reports generated in: {output}")
        click.echo(f"  Formats: {', '.join(format)}")

        # List generated files
        output_path = Path(output)
        for file in output_path.glob(f"{session}*"):
            click.echo(f"  - {file.name}")

    except Exception as e:
        click.echo(f"[ERROR] Report generation failed: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--session', required=True, help='Session ID')
@click.option('--output', default='ifmos/config/proposed_structure.yml', help='Output path for proposal')
@click.option('--db', default='db/ifmos.db', help='Database path')
@click.pass_context
def propose_structure(ctx, session, output, db):
    """Generate repository structure proposal based on scan analysis."""
    click.echo(f"[INFO] Generating structure proposal for session: {session}")

    # Initialize database and generator
    database = Database(db)
    generator = StructureProposalGenerator(database)

    # Generate proposal
    try:
        proposal = generator.generate_proposal(session, output)

        click.echo(f"\n[SUCCESS] Structure proposal generated!")
        click.echo(f"  Output file: {output}")
        click.echo(f"\n[STATS] Session Analysis:")
        click.echo(f"  Total files: {proposal['session_stats']['total_files']:,}")
        click.echo(f"  Total size: {proposal['session_stats']['total_size_gb']:.2f} GB")
        click.echo(f"  Categories: {proposal['session_stats']['categories']}")
        click.echo(f"\n[NEXT] Review and customize '{output}' then run:")
        click.echo(f"  ifmos plan --session {session} --structure {output}")

    except Exception as e:
        click.echo(f"[ERROR] Structure proposal failed: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option('--session', required=True, help='Session ID')
@click.option('--structure', default='ifmos/config/new_structure.yml', help='Target structure config')
@click.option('--output', help='Plan ID (auto-generated if not provided)')
@click.option('--db', default='db/ifmos.db', help='Database path')
@click.pass_context
def plan(ctx, session, structure, output, db):
    """Create migration plan."""
    click.echo(f"[INFO] Creating migration plan for session: {session}")

    # Load structure config
    structure_path = Path(structure)
    if not structure_path.exists():
        click.echo(f"[ERROR] Structure config not found: {structure}", err=True)
        raise click.Abort()

    with open(structure_path) as f:
        structure_config = yaml.safe_load(f)

    # Initialize database and planner
    database = Database(db)
    planner = MigrationPlanner(database, ctx.obj)

    # Create plan
    try:
        plan_id = planner.create_plan(session, structure_config)

        summary = planner.get_plan_summary(plan_id)

        click.echo(f"[SUCCESS] Migration plan created!")
        click.echo(f"  Plan ID: {plan_id}")
        click.echo(f"\nActions by type:")

        for action_type, stats in summary['actions_by_type'].items():
            click.echo(f"  {action_type}: {stats['count']:,} files ({stats['total_size_gb']:.2f} GB)")

        click.echo(f"\nRun 'ifmos dry-run --plan {plan_id}' to preview changes")

    except Exception as e:
        click.echo(f"[ERROR] Plan creation failed: {e}", err=True)
        raise click.Abort()


@cli.command('dry-run')
@click.option('--plan', required=True, help='Plan ID')
@click.option('--db', default='db/ifmos.db', help='Database path')
def dry_run(plan, db):
    """Preview migration plan without making changes."""
    click.echo(f"[INFO] Running dry-run for plan: {plan}")

    database = Database(db)
    executor = MigrationExecutor(database)

    # Show sample actions
    cursor = database.conn.cursor()
    cursor.execute("""
        SELECT source_path, target_path, action_type, reason
        FROM migration_actions
        WHERE plan_id = ?
        LIMIT 10
    """, (plan,))

    click.echo("\n[PREVIEW] Sample actions:")
    for i, row in enumerate(cursor.fetchall(), 1):
        source, target, action, reason = row
        click.echo(f"\n{i}. {action.upper()}: {source}")
        click.echo(f"   TO: {target}")
        click.echo(f"   REASON: {reason}")

    # Get total stats
    cursor.execute("""
        SELECT COUNT(*), SUM(file_size)
        FROM migration_actions
        WHERE plan_id = ?
    """, (plan,))

    count, total_size = cursor.fetchone()

    click.echo(f"\n[INFO] Total actions: {count:,}")
    click.echo(f"[INFO] Total data: {total_size / 1e9:.2f} GB")
    click.echo(f"\nRun 'ifmos approve --plan {plan}' to approve, then 'ifmos execute --plan {plan}' to execute")


@cli.command()
@click.option('--plan', required=True, help='Plan ID')
@click.option('--db', default='db/ifmos.db', help='Database path')
def approve(plan, db):
    """Approve a migration plan for execution."""
    database = Database(db)

    cursor = database.conn.cursor()
    cursor.execute("""
        UPDATE migration_plans
        SET approved = 1
        WHERE plan_id = ?
    """, (plan,))
    database.conn.commit()

    click.echo(f"[SUCCESS] Plan {plan} approved for execution")


@cli.command()
@click.option('--plan', required=True, help='Plan ID')
@click.option('--db', default='db/ifmos.db', help='Database path')
@click.confirmation_option(prompt='This will modify files. Continue?')
def execute(plan, db):
    """Execute an approved migration plan."""
    click.echo(f"[INFO] Executing migration plan: {plan}")

    database = Database(db)
    executor = MigrationExecutor(database)

    try:
        results = executor.execute_plan(plan)

        click.echo(f"[SUCCESS] Migration completed!")
        click.echo(f"  Successful: {results['successful']:,}")
        click.echo(f"  Failed: {results['failed']:,}")

        if results['errors']:
            click.echo("\nErrors:")
            for error in results['errors'][:5]:
                click.echo(f"  - {error['action_id']}: {error['error']}")

    except Exception as e:
        click.echo(f"[ERROR] Migration failed: {e}", err=True)
        click.echo("Attempting rollback...")
        raise click.Abort()


@cli.command()
@click.option('--db', default='db/ifmos.db', help='Database path')
def list_sessions(db):
    """List all scan sessions."""
    database = Database(db)

    cursor = database.conn.cursor()
    cursor.execute("""
        SELECT session_id, started_at, completed_at, files_scanned, status
        FROM scan_sessions
        ORDER BY started_at DESC
    """)

    click.echo("\nScan Sessions:")
    click.echo("=" * 80)

    for row in cursor.fetchall():
        session_id, started, completed, files, status = row
        click.echo(f"\nSession: {session_id}")
        click.echo(f"  Started: {started}")
        click.echo(f"  Completed: {completed or 'In progress'}")
        click.echo(f"  Files: {files:,}")
        click.echo(f"  Status: {status}")


def main():
    """Entry point for CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()

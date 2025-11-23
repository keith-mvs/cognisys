"""
Example usage of IFMOS programmatically (without CLI).
Demonstrates how to use the core components directly in Python scripts.
"""

import yaml
from pathlib import Path
from ifmos.models.database import Database
from ifmos.core.scanner import FileScanner
from ifmos.core.analyzer import Analyzer
from ifmos.core.reporter import Reporter
from ifmos.core.migrator import MigrationPlanner, MigrationExecutor
from ifmos.utils.logging_config import setup_logging


def main():
    """Example workflow using IFMOS programmatically."""

    # Setup logging
    setup_logging(level='INFO')

    # Load configuration
    with open('ifmos/config/scan_config.yml') as f:
        scan_config = yaml.safe_load(f)

    with open('ifmos/config/analysis_rules.yml') as f:
        analysis_config = yaml.safe_load(f)

    with open('ifmos/config/new_structure.yml') as f:
        structure_config = yaml.safe_load(f)

    # Initialize database
    db = Database('db/example.db')

    # Step 1: Scan file system
    print("\n=== Step 1: Scanning ===")
    scanner = FileScanner(db, scan_config)

    # Define roots to scan
    roots = [
        str(Path.home() / 'Documents'),
        str(Path.home() / 'Downloads')
    ]

    session_id = scanner.scan_roots(roots)
    print(f"Scan complete. Session ID: {session_id}")
    print(f"Stats: {scanner.get_stats()}")

    # Step 2: Analyze for duplicates
    print("\n=== Step 2: Analyzing ===")
    analyzer = Analyzer(db, analysis_config)
    analysis_stats = analyzer.analyze_session(session_id)
    print(f"Analysis complete: {analysis_stats}")

    # Step 3: Generate reports
    print("\n=== Step 3: Reporting ===")
    reporter = Reporter(db, {})
    reporter.generate_report(session_id, 'reports', formats=['html', 'json'])
    print("Reports generated in 'reports/' directory")

    # Step 4: Create migration plan
    print("\n=== Step 4: Migration Planning ===")
    planner = MigrationPlanner(db, analysis_config)
    plan_id = planner.create_plan(session_id, structure_config)
    print(f"Migration plan created: {plan_id}")

    summary = planner.get_plan_summary(plan_id)
    print(f"Plan summary: {summary}")

    # Step 5: Execute migration (with confirmation)
    print("\n=== Step 5: Migration Execution ===")
    response = input("Execute migration? This will modify files. (yes/no): ")

    if response.lower() == 'yes':
        # Approve plan
        cursor = db.conn.cursor()
        cursor.execute("UPDATE migration_plans SET approved = 1 WHERE plan_id = ?", (plan_id,))
        db.conn.commit()

        # Execute
        executor = MigrationExecutor(db)
        results = executor.execute_plan(plan_id)
        print(f"Migration complete: {results}")
    else:
        print("Migration cancelled. Run dry-run to preview changes.")

    # Close database
    db.close()
    print("\n=== Workflow Complete ===")


if __name__ == '__main__':
    main()

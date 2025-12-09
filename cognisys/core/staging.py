"""
Staging system for CogniSys - Preview organization before commit.
Implements Inbox → Staging → Current workflow with full rollback support.
"""

import os
import shutil
import json
import uuid
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum

from ..models.database import Database
from ..utils.naming import apply_naming_convention, sanitize_name
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class StagingMethod(Enum):
    """Methods for staging files."""
    SYMLINK = "symlink"      # Symbolic links (fast, no space)
    HARDLINK = "hardlink"    # Hard links (fast, no space, Windows compatible)
    COPY = "copy"            # Full copy (slow, uses space, safest)


class StagingStatus(Enum):
    """Staging plan statuses."""
    DRAFT = "draft"
    STAGED = "staged"
    VALIDATED = "validated"
    COMMITTED = "committed"
    DISCARDED = "discarded"
    FAILED = "failed"


class ConflictStrategy(Enum):
    """Strategies for resolving file conflicts."""
    ASK = "ask"              # Prompt user
    SKIP = "skip"            # Skip conflicting file
    RENAME = "rename"        # Add suffix (_1, _2, etc)
    REPLACE = "replace"      # Overwrite existing
    KEEP_NEWEST = "newest"   # Keep file with latest mtime
    KEEP_LARGEST = "largest" # Keep largest file


class StagingManager:
    """
    Manages staging workflow for file organization.
    Provides preview, validation, and safe commit of file migrations.
    """

    def __init__(self, database: Database, config: Dict):
        """
        Initialize staging manager.

        Args:
            database: Database instance
            config: Configuration dict
        """
        self.db = database
        self.config = config
        self.staging_root = Path(config.get('staging_root', '.cognisys/staging'))
        self.staging_root.mkdir(parents=True, exist_ok=True)

    def create_staging_plan(
        self,
        session_id: str,
        target_root: str,
        method: StagingMethod = StagingMethod.SYMLINK,
        structure_config: Optional[Dict] = None
    ) -> str:
        """
        Create a new staging plan.

        Args:
            session_id: Scan session ID
            target_root: Target organization root path
            method: Staging method (symlink, hardlink, copy)
            structure_config: Target structure configuration

        Returns:
            Staging plan ID
        """
        logger.info(f"Creating staging plan for session {session_id}")

        plan_id = f"stage-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        staging_path = self.staging_root / plan_id
        staging_path.mkdir(parents=True, exist_ok=True)

        # Create plan record
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO staging_plans (plan_id, created_at, session_id, staging_root, target_root, status, method)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (plan_id, datetime.now(), session_id, str(staging_path), target_root, StagingStatus.DRAFT.value, method.value))
        self.db.conn.commit()

        # Generate staging actions
        if structure_config:
            self._generate_staging_actions(plan_id, session_id, target_root, structure_config)

        logger.info(f"Staging plan {plan_id} created at {staging_path}")
        return plan_id

    def _generate_staging_actions(
        self,
        plan_id: str,
        session_id: str,
        target_root: str,
        structure_config: Dict
    ):
        """Generate staging actions based on file classification."""
        cursor = self.db.conn.cursor()

        # Get files from session (non-duplicates, non-temp)
        cursor.execute("""
            SELECT file_id, path, name, file_category, classified_category, size_bytes
            FROM files
            WHERE scan_session_id = ?
              AND is_duplicate = 0
              AND is_temp = 0
              AND is_orphaned = 0
        """, (session_id,))

        files = cursor.fetchall()
        logger.info(f"Generating actions for {len(files)} files")

        classification = structure_config.get('classification', {})
        staging_path = self.staging_root / plan_id

        for file_row in files:
            file_id, file_path, name, file_cat, classified_cat, size_bytes = file_row

            # Use classified category if available, else file category
            category = classified_cat if classified_cat else file_cat

            if category and category in classification:
                # Compute target path
                target_path = self._compute_target_path(
                    file_id=file_id,
                    name=name,
                    category=category,
                    classification_rule=classification[category],
                    target_root=target_root
                )

                # Compute staging path (mirrors target)
                staging_file_path = staging_path / Path(target_path).relative_to(target_root) if Path(target_path).is_absolute() else staging_path / target_path

                # Check for conflicts
                conflict_type = None
                if Path(target_path).exists():
                    conflict_type = 'existing_file'

                # Add staging action
                cursor.execute("""
                    INSERT INTO staging_actions (
                        plan_id, source_path, staging_path, target_path,
                        action_type, status, conflict_type
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    plan_id,
                    file_path,
                    str(staging_file_path),
                    target_path,
                    'move',
                    'pending',
                    conflict_type
                ))

        self.db.conn.commit()

        # Get action count
        cursor.execute("SELECT COUNT(*) FROM staging_actions WHERE plan_id = ?", (plan_id,))
        action_count = cursor.fetchone()[0]

        # Get conflict count
        cursor.execute("""
            SELECT COUNT(*) FROM staging_actions
            WHERE plan_id = ? AND conflict_type IS NOT NULL
        """, (plan_id,))
        conflict_count = cursor.fetchone()[0]

        logger.info(f"Generated {action_count} actions ({conflict_count} conflicts)")

    def _compute_target_path(
        self,
        file_id: str,
        name: str,
        category: str,
        classification_rule: Dict,
        target_root: str
    ) -> str:
        """Compute target path for file based on category rules."""
        # Simple implementation - use category as subfolder
        category_path = classification_rule.get('path_template', category.replace('_', '/'))
        target_path = Path(target_root) / category_path / name
        return str(target_path)

    def stage(self, plan_id: str) -> Dict:
        """
        Execute staging - create symlinks/copies in staging directory.

        Args:
            plan_id: Staging plan ID

        Returns:
            Staging results dict
        """
        logger.info(f"Staging plan {plan_id}")

        cursor = self.db.conn.cursor()

        # Get plan details
        cursor.execute("""
            SELECT staging_root, method, status
            FROM staging_plans
            WHERE plan_id = ?
        """, (plan_id,))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Staging plan {plan_id} not found")

        staging_root, method, status = row

        if status != StagingStatus.DRAFT.value:
            raise ValueError(f"Plan {plan_id} status is {status}, expected {StagingStatus.DRAFT.value}")

        # Get staging actions
        cursor.execute("""
            SELECT action_id, source_path, staging_path, conflict_type
            FROM staging_actions
            WHERE plan_id = ? AND status = 'pending'
        """, (plan_id,))

        actions = cursor.fetchall()

        results = {
            'plan_id': plan_id,
            'total': len(actions),
            'staged': 0,
            'skipped': 0,
            'failed': 0,
            'conflicts': 0
        }

        for action_id, source_path, staging_path, conflict_type in actions:
            try:
                # Skip if conflict and not resolved
                if conflict_type:
                    logger.warning(f"Skipping {source_path} due to conflict: {conflict_type}")
                    results['conflicts'] += 1
                    results['skipped'] += 1
                    continue

                # Create staging file
                staging_file = Path(staging_path)
                staging_file.parent.mkdir(parents=True, exist_ok=True)

                if method == StagingMethod.SYMLINK.value:
                    self._create_symlink(source_path, staging_path)
                elif method == StagingMethod.HARDLINK.value:
                    self._create_hardlink(source_path, staging_path)
                elif method == StagingMethod.COPY.value:
                    shutil.copy2(source_path, staging_path)

                # Update action status
                cursor.execute("""
                    UPDATE staging_actions
                    SET status = 'staged'
                    WHERE action_id = ?
                """, (action_id,))

                results['staged'] += 1

            except Exception as e:
                logger.error(f"Failed to stage {source_path}: {e}")
                cursor.execute("""
                    UPDATE staging_actions
                    SET status = 'failed', validation_errors = ?
                    WHERE action_id = ?
                """, (str(e), action_id))
                results['failed'] += 1

        # Update plan status
        if results['failed'] == 0 and results['conflicts'] == 0:
            new_status = StagingStatus.STAGED.value
        else:
            new_status = StagingStatus.DRAFT.value  # Keep in draft if issues

        cursor.execute("""
            UPDATE staging_plans
            SET status = ?
            WHERE plan_id = ?
        """, (new_status, plan_id))

        self.db.conn.commit()

        logger.info(f"Staging complete: {results['staged']} staged, {results['skipped']} skipped, {results['failed']} failed")
        return results

    def _create_symlink(self, source: str, target: str):
        """Create symbolic link (Unix) or junction (Windows)."""
        source_path = Path(source).resolve()
        target_path = Path(target)

        if os.name == 'nt':  # Windows
            # Use junction for directories, symlink for files
            if source_path.is_dir():
                subprocess.run(['mklink', '/J', str(target_path), str(source_path)], shell=True, check=True)
            else:
                os.symlink(source_path, target_path)
        else:  # Unix
            os.symlink(source_path, target_path)

    def _create_hardlink(self, source: str, target: str):
        """Create hard link."""
        os.link(source, target)

    def validate(self, plan_id: str) -> Dict:
        """
        Validate staging plan before commit.

        Args:
            plan_id: Staging plan ID

        Returns:
            Validation results dict
        """
        logger.info(f"Validating staging plan {plan_id}")

        cursor = self.db.conn.cursor()

        # Get plan status
        cursor.execute("SELECT status FROM staging_plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Plan {plan_id} not found")

        status = row[0]
        if status != StagingStatus.STAGED.value:
            raise ValueError(f"Plan must be staged first (current status: {status})")

        results = {
            'plan_id': plan_id,
            'checks': {},
            'errors': [],
            'warnings': [],
            'passed': True
        }

        # Check 1: Source files readable
        cursor.execute("""
            SELECT action_id, source_path
            FROM staging_actions
            WHERE plan_id = ? AND status = 'staged'
        """, (plan_id,))

        unreadable = []
        for action_id, source_path in cursor.fetchall():
            if not os.access(source_path, os.R_OK):
                unreadable.append(source_path)

        results['checks']['source_readable'] = len(unreadable) == 0
        if unreadable:
            results['errors'].append(f"{len(unreadable)} source files not readable")
            results['passed'] = False

        # Check 2: Target paths valid
        cursor.execute("""
            SELECT action_id, target_path
            FROM staging_actions
            WHERE plan_id = ? AND status = 'staged'
        """, (plan_id,))

        invalid_paths = []
        for action_id, target_path in cursor.fetchall():
            if len(target_path) > 260 and os.name == 'nt':  # Windows path length limit
                invalid_paths.append(target_path)

        results['checks']['path_valid'] = len(invalid_paths) == 0
        if invalid_paths:
            results['errors'].append(f"{len(invalid_paths)} paths exceed Windows 260 char limit")
            results['passed'] = False

        # Check 3: Disk space sufficient
        cursor.execute("""
            SELECT SUM(files.size_bytes)
            FROM staging_actions sa
            JOIN files ON sa.source_path = files.path
            WHERE sa.plan_id = ? AND sa.status = 'staged'
        """, (plan_id,))

        row = cursor.fetchone()
        required_space = row[0] if row and row[0] else 0

        cursor.execute("SELECT target_root FROM staging_plans WHERE plan_id = ?", (plan_id,))
        target_root = cursor.fetchone()[0]

        if os.path.exists(target_root):
            stat = shutil.disk_usage(target_root)
            available_space = stat.free

            results['checks']['disk_space'] = available_space > required_space * 1.1  # 10% buffer
            results['required_space_gb'] = required_space / 1e9
            results['available_space_gb'] = available_space / 1e9

            if available_space < required_space * 1.1:
                results['errors'].append(f"Insufficient disk space: {available_space/1e9:.1f} GB available, {required_space/1e9:.1f} GB required")
                results['passed'] = False

        # Check 4: Conflicts resolved
        cursor.execute("""
            SELECT COUNT(*)
            FROM staging_actions
            WHERE plan_id = ? AND conflict_type IS NOT NULL AND resolution_strategy IS NULL
        """, (plan_id,))

        unresolved_conflicts = cursor.fetchone()[0]
        results['checks']['conflicts_resolved'] = unresolved_conflicts == 0
        if unresolved_conflicts > 0:
            results['errors'].append(f"{unresolved_conflicts} unresolved conflicts")
            results['passed'] = False

        # Update plan status
        if results['passed']:
            cursor.execute("""
                UPDATE staging_plans
                SET status = ?
                WHERE plan_id = ?
            """, (StagingStatus.VALIDATED.value, plan_id))
            self.db.conn.commit()

        logger.info(f"Validation {'passed' if results['passed'] else 'failed'} for plan {plan_id}")
        return results

    def commit(self, plan_id: str, create_snapshot: bool = True) -> Dict:
        """
        Commit staging plan - move files to production.

        Args:
            plan_id: Staging plan ID
            create_snapshot: Create snapshot before commit

        Returns:
            Commit results dict
        """
        logger.info(f"Committing staging plan {plan_id}")

        cursor = self.db.conn.cursor()

        # Verify plan is validated
        cursor.execute("SELECT status, target_root FROM staging_plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Plan {plan_id} not found")

        status, target_root = row
        if status != StagingStatus.VALIDATED.value:
            raise ValueError(f"Plan must be validated first (current status: {status})")

        # Create snapshot if requested
        snapshot_id = None
        if create_snapshot:
            snapshot_id = self._create_snapshot(plan_id, target_root)

        # Get staged actions
        cursor.execute("""
            SELECT action_id, source_path, target_path, action_type
            FROM staging_actions
            WHERE plan_id = ? AND status = 'staged'
        """, (plan_id,))

        actions = cursor.fetchall()

        results = {
            'plan_id': plan_id,
            'snapshot_id': snapshot_id,
            'total': len(actions),
            'committed': 0,
            'failed': 0,
            'errors': []
        }

        for action_id, source_path, target_path, action_type in actions:
            try:
                # Create target directory
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)

                # Move file to target
                if action_type == 'move':
                    shutil.move(source_path, target_path)
                elif action_type == 'copy':
                    shutil.copy2(source_path, target_path)

                # Update action status
                cursor.execute("""
                    UPDATE staging_actions
                    SET status = 'committed'
                    WHERE action_id = ?
                """, (action_id,))

                results['committed'] += 1

            except Exception as e:
                logger.error(f"Failed to commit {source_path}: {e}")
                results['failed'] += 1
                results['errors'].append({
                    'action_id': action_id,
                    'source': source_path,
                    'error': str(e)
                })

        # Update plan status
        cursor.execute("""
            UPDATE staging_plans
            SET status = ?, committed_at = ?
            WHERE plan_id = ?
        """, (StagingStatus.COMMITTED.value, datetime.now(), plan_id))

        self.db.conn.commit()

        logger.info(f"Commit complete: {results['committed']} committed, {results['failed']} failed")
        return results

    def discard(self, plan_id: str) -> Dict:
        """
        Discard staging plan - remove staging directory.

        Args:
            plan_id: Staging plan ID

        Returns:
            Discard results dict
        """
        logger.info(f"Discarding staging plan {plan_id}")

        cursor = self.db.conn.cursor()

        # Get staging root
        cursor.execute("SELECT staging_root, status FROM staging_plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Plan {plan_id} not found")

        staging_root, status = row

        if status == StagingStatus.COMMITTED.value:
            raise ValueError(f"Cannot discard committed plan")

        # Remove staging directory
        if Path(staging_root).exists():
            shutil.rmtree(staging_root)

        # Update plan status
        cursor.execute("""
            UPDATE staging_plans
            SET status = ?
            WHERE plan_id = ?
        """, (StagingStatus.DISCARDED.value, plan_id))

        self.db.conn.commit()

        logger.info(f"Staging plan {plan_id} discarded")
        return {'plan_id': plan_id, 'status': 'discarded'}

    def _create_snapshot(self, plan_id: str, root_path: str) -> str:
        """Create snapshot before migration."""
        snapshot_id = f"snap-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO snapshots (snapshot_id, created_at, snapshot_type, plan_id, root_path)
            VALUES (?, ?, ?, ?, ?)
        """, (snapshot_id, datetime.now(), 'before_migration', plan_id, root_path))

        self.db.conn.commit()

        logger.info(f"Snapshot {snapshot_id} created")
        return snapshot_id

    def get_plan_summary(self, plan_id: str) -> Dict:
        """Get summary of staging plan."""
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT sp.*, COUNT(sa.action_id) as action_count
            FROM staging_plans sp
            LEFT JOIN staging_actions sa ON sp.plan_id = sa.plan_id
            WHERE sp.plan_id = ?
            GROUP BY sp.plan_id
        """, (plan_id,))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Plan {plan_id} not found")

        summary = dict(row)

        # Get conflict count
        cursor.execute("""
            SELECT COUNT(*) FROM staging_actions
            WHERE plan_id = ? AND conflict_type IS NOT NULL
        """, (plan_id,))
        summary['conflict_count'] = cursor.fetchone()[0]

        return summary

"""
Migration engine for CogniSys.
Plans and executes file reorganization with safety checks and rollback support.
"""

import os
import shutil
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from ..models.database import Database
from ..utils.naming import apply_naming_convention, sanitize_name, extract_version, extract_project_name
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class MigrationPlanner:
    """
    Generates migration plans based on analysis results and target structure.
    """

    def __init__(self, database: Database, config: Dict):
        """
        Initialize migration planner.

        Args:
            database: Database instance
            config: Configuration with structure rules
        """
        self.db = database
        self.config = config

    def create_plan(self, session_id: str, structure_config: Dict) -> str:
        """
        Create a migration plan for reorganizing files.

        Args:
            session_id: Scan session ID
            structure_config: Target repository structure configuration

        Returns:
            Plan ID
        """
        logger.info(f"Creating migration plan for session {session_id}")

        plan_id = f"plan-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"

        # Create plan record
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO migration_plans (plan_id, created_at, session_id, status)
            VALUES (?, ?, ?, ?)
        """, (plan_id, datetime.now(), session_id, 'draft'))
        self.db.conn.commit()

        # Generate actions
        self._generate_duplicate_actions(plan_id, session_id)
        self._generate_reorganization_actions(plan_id, session_id, structure_config)
        self._generate_archive_actions(plan_id, session_id, structure_config)

        logger.info(f"Migration plan {plan_id} created")
        return plan_id

    def _generate_duplicate_actions(self, plan_id: str, session_id: str):
        """Generate actions for handling duplicates."""
        cursor = self.db.conn.cursor()

        # Get all duplicate groups
        cursor.execute("""
            SELECT dg.group_id, dg.canonical_file
            FROM duplicate_groups dg
            JOIN files f ON dg.canonical_file = f.file_id
            WHERE f.scan_session_id = ?
        """, (session_id,))

        for row in cursor.fetchall():
            group_id, canonical_id = row

            # Get all members except canonical
            cursor.execute("""
                SELECT f.*
                FROM duplicate_members dm
                JOIN files f ON dm.file_id = f.file_id
                WHERE dm.group_id = ? AND dm.file_id != ?
            """, (group_id, canonical_id))

            for file_row in cursor.fetchall():
                file = dict(file_row)
                target_path = Path("Quarantine") / f"Duplicates_{datetime.now().strftime('%Y-%m-%d')}" / file['name']

                self._add_action(
                    plan_id=plan_id,
                    source_path=file['path'],
                    target_path=str(target_path),
                    action_type='move',
                    rule_id='duplicate_quarantine',
                    reason=f"Duplicate (group {group_id})",
                    file_size=file['size_bytes']
                )

    def _generate_reorganization_actions(self, plan_id: str, session_id: str, structure_config: Dict):
        """Generate actions for reorganizing files by category."""
        cursor = self.db.conn.cursor()

        # Get files that need reorganization (not duplicates, not orphaned)
        cursor.execute("""
            SELECT * FROM files
            WHERE scan_session_id = ?
              AND is_duplicate = 0
              AND is_orphaned = 0
              AND is_temp = 0
        """, (session_id,))

        repo_root = structure_config.get('repository_root', 'C:\\Repository')
        classification = structure_config.get('classification', {})

        for row in cursor.fetchall():
            file = dict(row)

            # Determine target path based on category
            category = file['file_category']
            if category in classification:
                target_path = self._compute_target_path(file, classification[category], repo_root)

                if target_path and target_path != file['path']:
                    self._add_action(
                        plan_id=plan_id,
                        source_path=file['path'],
                        target_path=target_path,
                        action_type='move',
                        rule_id=f'reorganize_{category}',
                        reason=f'Reorganize to {category} structure',
                        file_size=file['size_bytes']
                    )

    def _generate_archive_actions(self, plan_id: str, session_id: str, structure_config: Dict):
        """Generate actions for archiving stale files."""
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT * FROM files
            WHERE scan_session_id = ?
              AND is_orphaned = 1
        """, (session_id,))

        repo_root = structure_config.get('repository_root', 'C:\\Repository')

        for row in cursor.fetchall():
            file = dict(row)

            target_path = Path(repo_root) / 'Archive' / file['file_category'] / \
                         datetime.now().strftime('%Y') / file['name']

            self._add_action(
                plan_id=plan_id,
                source_path=file['path'],
                target_path=str(target_path),
                action_type='move',
                rule_id='lifecycle_archive',
                reason=f'Orphaned file (not accessed recently)',
                file_size=file['size_bytes']
            )

    def _compute_target_path(self, file: Dict, category_config: Dict, repo_root: str) -> Optional[str]:
        """
        Compute target path for a file based on category rules.

        Args:
            file: File record
            category_config: Category configuration
            repo_root: Repository root path

        Returns:
            Target path string or None
        """
        target_template = category_config.get('target')
        if not target_template:
            return None

        # Extract context variables
        modified_date = datetime.fromisoformat(file['modified_at']) if isinstance(file['modified_at'], str) else file['modified_at']

        context = {
            'YYYY': modified_date.strftime('%Y'),
            'MM': modified_date.strftime('%m'),
            'YYYY-MM': modified_date.strftime('%Y-%m'),
            'subcategory': 'General',
            'media_type': file['file_category'],
            'project_name': extract_project_name(file['path']) or 'General'
        }

        # Render template
        try:
            target_dir = target_template.format(**context)
        except KeyError:
            target_dir = f"Active/{file['file_category']}"

        # Apply naming convention if enabled
        naming_config = self.config.get('naming_conventions', {})
        if naming_config.get('files', {}).get('pattern'):
            new_filename = apply_naming_convention(
                file['name'],
                modified_date.strftime('%Y-%m-%d'),
                context['project_name'],
                file['file_category'],
                extract_version(file['name']) or 'v01',
                file['extension']
            )
        else:
            new_filename = file['name']

        full_path = Path(repo_root) / target_dir / new_filename
        return str(full_path)

    def _add_action(
        self,
        plan_id: str,
        source_path: str,
        target_path: str,
        action_type: str,
        rule_id: str,
        reason: str,
        file_size: int
    ):
        """Add an action to the migration plan."""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO migration_actions
            (action_id, plan_id, source_path, target_path, action_type,
             rule_id, reason, file_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            plan_id,
            source_path,
            target_path,
            action_type,
            rule_id,
            reason,
            file_size
        ))
        self.db.conn.commit()

    def get_plan_summary(self, plan_id: str) -> Dict:
        """Get summary of a migration plan."""
        cursor = self.db.conn.cursor()

        cursor.execute("""
            SELECT action_type, COUNT(*) as count, SUM(file_size) as total_size
            FROM migration_actions
            WHERE plan_id = ?
            GROUP BY action_type
        """, (plan_id,))

        summary = {
            'plan_id': plan_id,
            'actions_by_type': {}
        }

        for row in cursor.fetchall():
            action_type, count, total_size = row
            summary['actions_by_type'][action_type] = {
                'count': count,
                'total_size_gb': total_size / 1e9 if total_size else 0
            }

        return summary


class MigrationExecutor:
    """
    Executes migration plans with safety checks and rollback support.
    """

    def __init__(self, database: Database):
        """
        Initialize migration executor.

        Args:
            database: Database instance
        """
        self.db = database

    def execute_plan(self, plan_id: str, dry_run: bool = False) -> Dict:
        """
        Execute a migration plan.

        Args:
            plan_id: Plan ID to execute
            dry_run: If True, simulate without making changes

        Returns:
            Execution results
        """
        logger.info(f"{'Dry run' if dry_run else 'Executing'} migration plan {plan_id}")

        cursor = self.db.conn.cursor()

        # Check if plan is approved
        cursor.execute("SELECT approved, status FROM migration_plans WHERE plan_id = ?", (plan_id,))
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Plan {plan_id} not found")

        approved, status = row

        if not approved and not dry_run:
            raise ValueError(f"Plan {plan_id} must be approved before execution")

        # Get all actions
        cursor.execute("""
            SELECT * FROM migration_actions
            WHERE plan_id = ?
            ORDER BY action_id
        """, (plan_id,))

        actions = [dict(row) for row in cursor.fetchall()]

        results = {
            'total_actions': len(actions),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        if dry_run:
            logger.info(f"Dry run: {len(actions)} actions would be executed")
            return results

        # Create checkpoint
        checkpoint_file = Path('checkpoints') / f"{plan_id}.json"
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        checkpoint_data = {
            'plan_id': plan_id,
            'created_at': datetime.now().isoformat(),
            'actions': []
        }

        try:
            # Execute actions
            for action in actions:
                try:
                    if action['action_type'] == 'move':
                        self._execute_move(action)
                    elif action['action_type'] == 'copy':
                        self._execute_copy(action)
                    elif action['action_type'] == 'delete':
                        self._execute_delete(action)

                    # Mark as executed
                    cursor.execute("""
                        UPDATE migration_actions
                        SET executed = 1, execution_time = ?
                        WHERE action_id = ?
                    """, (datetime.now(), action['action_id']))

                    results['successful'] += 1

                    # Add to checkpoint
                    checkpoint_data['actions'].append({
                        'action_id': action['action_id'],
                        'source': action['source_path'],
                        'target': action['target_path'],
                        'type': action['action_type']
                    })

                except Exception as e:
                    logger.error(f"Action {action['action_id']} failed: {e}")
                    results['failed'] += 1
                    results['errors'].append({
                        'action_id': action['action_id'],
                        'error': str(e)
                    })

                # Periodic checkpoint save
                if results['successful'] % 100 == 0:
                    with open(checkpoint_file, 'w') as f:
                        json.dump(checkpoint_data, f, indent=2)

            # Final checkpoint save
            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            # Update plan status
            cursor.execute("""
                UPDATE migration_plans
                SET status = ?, executed_at = ?
                WHERE plan_id = ?
            """, ('completed', datetime.now(), plan_id))

            self.db.conn.commit()

            logger.info(f"Migration completed: {results['successful']} successful, {results['failed']} failed")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            # Attempt rollback
            self._rollback(checkpoint_file)
            raise

        return results

    def _execute_move(self, action: Dict):
        """Execute a move action."""
        source = Path(action['source_path'])
        target = Path(action['target_path'])

        if not source.exists():
            raise FileNotFoundError(f"Source not found: {source}")

        # Create target directory
        target.parent.mkdir(parents=True, exist_ok=True)

        # Handle name conflicts
        if target.exists():
            target = self._resolve_conflict(target)

        # Move file
        shutil.move(str(source), str(target))

        logger.debug(f"Moved: {source} -> {target}")

    def _execute_copy(self, action: Dict):
        """Execute a copy action."""
        source = Path(action['source_path'])
        target = Path(action['target_path'])

        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            target = self._resolve_conflict(target)

        shutil.copy2(str(source), str(target))

        logger.debug(f"Copied: {source} -> {target}")

    def _execute_delete(self, action: Dict):
        """Execute a delete action (move to trash)."""
        source = Path(action['source_path'])

        if not source.exists():
            return

        # Move to trash instead of permanent delete
        trash_dir = Path('Quarantine') / 'Trash'
        trash_dir.mkdir(parents=True, exist_ok=True)

        trash_path = trash_dir / source.name
        if trash_path.exists():
            trash_path = self._resolve_conflict(trash_path)

        shutil.move(str(source), str(trash_path))

        logger.debug(f"Deleted (moved to trash): {source}")

    def _resolve_conflict(self, path: Path) -> Path:
        """Resolve naming conflict by adding suffix."""
        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1

    def _rollback(self, checkpoint_file: Path):
        """Rollback changes using checkpoint."""
        if not checkpoint_file.exists():
            logger.error("No checkpoint file found for rollback")
            return

        with open(checkpoint_file) as f:
            checkpoint = json.load(f)

        logger.info(f"Rolling back {len(checkpoint['actions'])} actions")

        for action in reversed(checkpoint['actions']):
            try:
                if action['type'] == 'move':
                    # Move back
                    target = Path(action['target'])
                    source = Path(action['source'])

                    if target.exists():
                        shutil.move(str(target), str(source))

            except Exception as e:
                logger.error(f"Rollback action failed: {e}")

        logger.info("Rollback completed")

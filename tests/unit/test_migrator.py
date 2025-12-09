"""
Unit Tests for Migrator
Tests migration planning, execution, and rollback functionality
"""

import pytest
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

from cognisys.core.migrator import MigrationPlanner, MigrationExecutor
from cognisys.models.database import Database


class TestMigrationPlanner:
    """Test MigrationPlanner functionality."""

    def test_planner_initialization(self, temp_db, migrator_config):
        """Planner should initialize correctly."""
        planner = MigrationPlanner(temp_db, migrator_config)

        assert planner.db == temp_db
        assert planner.config == migrator_config

    def test_create_plan_generates_id(self, temp_db, migrator_config, structure_config):
        """Create plan should generate a valid plan ID."""
        session_id = temp_db.create_session(['/test'], {})

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        assert plan_id is not None
        assert plan_id.startswith('plan-')
        assert len(plan_id) > 15

    def test_create_plan_stores_in_database(self, temp_db, migrator_config, structure_config):
        """Create plan should store plan record in database."""
        session_id = temp_db.create_session(['/test'], {})

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT * FROM migration_plans WHERE plan_id = ?", (plan_id,))
        result = cursor.fetchone()

        assert result is not None
        assert result['status'] == 'draft'
        assert result['session_id'] == session_id

    def test_get_plan_summary(self, temp_db, migrator_config, structure_config):
        """Get plan summary should return action counts."""
        session_id = temp_db.create_session(['/test'], {})

        # Add a file to generate actions
        temp_db.insert_file({
            'file_id': 'file-1',
            'path': '/test/file.txt',
            'name': 'file.txt',
            'extension': '.txt',
            'size_bytes': 1000,
            'file_category': 'document',
            'modified_at': datetime.now(),
            'is_duplicate': 0,
            'is_orphaned': 0,
            'is_temp': 0,
            'scan_session_id': session_id
        })

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        summary = planner.get_plan_summary(plan_id)

        assert 'plan_id' in summary
        assert 'actions_by_type' in summary


class TestDuplicateActions:
    """Test duplicate handling action generation."""

    def test_generate_duplicate_actions(self, temp_db, migrator_config, structure_config):
        """Should generate quarantine actions for duplicates."""
        session_id = temp_db.create_session(['/test'], {})

        # Insert files
        for i in range(3):
            temp_db.insert_file({
                'file_id': f'dup-{i}',
                'path': f'/test/file{i}.txt',
                'name': f'file{i}.txt',
                'extension': '.txt',
                'size_bytes': 1000,
                'scan_session_id': session_id
            })

        # Create a duplicate group
        group_data = {
            'canonical_file': 'dup-0',
            'member_count': 3,
            'total_size': 1000,
            'similarity_type': 'exact',
            'detection_rule': 'test',
            'members': [
                {'file_id': 'dup-0', 'priority_score': 100, 'reason': 'canonical'},
                {'file_id': 'dup-1', 'priority_score': 50, 'reason': 'duplicate'},
                {'file_id': 'dup-2', 'priority_score': 50, 'reason': 'duplicate'},
            ]
        }
        temp_db.create_duplicate_group(group_data)

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        # Check that quarantine actions were generated
        cursor = temp_db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as cnt FROM migration_actions
            WHERE plan_id = ? AND rule_id = 'duplicate_quarantine'
        """, (plan_id,))
        result = cursor.fetchone()

        assert result['cnt'] == 2  # 2 duplicates (not canonical)


class TestReorganizationActions:
    """Test file reorganization action generation."""

    def test_generate_reorganization_actions(self, temp_db, migrator_config, structure_config):
        """Should generate move actions based on category."""
        session_id = temp_db.create_session(['/test'], {})

        # Insert a document file
        temp_db.insert_file({
            'file_id': 'doc-1',
            'path': '/test/report.pdf',
            'name': 'report.pdf',
            'extension': '.pdf',
            'size_bytes': 5000,
            'file_category': 'document',
            'modified_at': datetime.now(),
            'is_duplicate': 0,
            'is_orphaned': 0,
            'is_temp': 0,
            'scan_session_id': session_id
        })

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        cursor = temp_db.conn.cursor()
        cursor.execute("""
            SELECT * FROM migration_actions
            WHERE plan_id = ? AND rule_id LIKE 'reorganize_%'
        """, (plan_id,))
        actions = cursor.fetchall()

        assert len(actions) >= 1

    def test_compute_target_path(self, temp_db, migrator_config, structure_config):
        """Should compute correct target path from template."""
        planner = MigrationPlanner(temp_db, migrator_config)

        file_record = {
            'path': '/test/report.pdf',
            'name': 'report.pdf',
            'extension': '.pdf',
            'file_category': 'document',
            'modified_at': datetime(2024, 3, 15)
        }

        category_config = {'target': 'Active/Documents/{YYYY}/{MM}'}

        target = planner._compute_target_path(
            file_record,
            category_config,
            structure_config['repository_root']
        )

        assert target is not None
        assert '2024' in target
        assert '03' in target


class TestArchiveActions:
    """Test archive action generation for orphaned files."""

    def test_generate_archive_actions(self, temp_db, migrator_config, structure_config):
        """Should generate archive actions for orphaned files."""
        session_id = temp_db.create_session(['/test'], {})

        # Insert a file first
        temp_db.insert_file({
            'file_id': 'orphan-1',
            'path': '/test/old_file.txt',
            'name': 'old_file.txt',
            'extension': '.txt',
            'size_bytes': 1000,
            'file_category': 'document',
            'modified_at': datetime.now(),
            'scan_session_id': session_id
        })

        # Mark it as orphaned (insert_file doesn't include is_orphaned)
        cursor = temp_db.conn.cursor()
        cursor.execute("UPDATE files SET is_orphaned = 1 WHERE file_id = ?", ('orphan-1',))
        temp_db.conn.commit()

        # Verify the file was marked as orphaned
        cursor.execute("SELECT * FROM files WHERE file_id = ?", ('orphan-1',))
        file_row = cursor.fetchone()
        assert file_row is not None
        assert file_row['is_orphaned'] == 1

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        cursor.execute("""
            SELECT * FROM migration_actions
            WHERE plan_id = ? AND rule_id = 'lifecycle_archive'
        """, (plan_id,))
        actions = cursor.fetchall()

        # Archive action should be generated for the orphaned file
        assert len(actions) == 1
        assert 'Archive' in actions[0]['target_path']


class TestMigrationExecutor:
    """Test MigrationExecutor functionality."""

    def test_executor_initialization(self, temp_db):
        """Executor should initialize correctly."""
        executor = MigrationExecutor(temp_db)
        assert executor.db == temp_db

    def test_execute_plan_requires_approval(self, temp_db, migrator_config, structure_config):
        """Execute plan should fail if not approved."""
        session_id = temp_db.create_session(['/test'], {})

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        executor = MigrationExecutor(temp_db)

        with pytest.raises(ValueError, match="must be approved"):
            executor.execute_plan(plan_id, dry_run=False)

    def test_execute_plan_dry_run(self, temp_db, migrator_config, structure_config):
        """Dry run should work without approval."""
        session_id = temp_db.create_session(['/test'], {})

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        executor = MigrationExecutor(temp_db)
        results = executor.execute_plan(plan_id, dry_run=True)

        assert 'total_actions' in results
        assert results['failed'] == 0

    def test_execute_plan_nonexistent(self, temp_db):
        """Execute should fail for nonexistent plan."""
        executor = MigrationExecutor(temp_db)

        with pytest.raises(ValueError, match="not found"):
            executor.execute_plan('nonexistent-plan')


class TestMoveAction:
    """Test file move action execution."""

    def test_execute_move_action(self, temp_db, temp_dir):
        """Should move file to target location."""
        # Create source file
        source = temp_dir / "source.txt"
        source.write_text("content")

        target_dir = temp_dir / "target"
        target = target_dir / "moved.txt"

        action = {
            'action_id': 'act-1',
            'source_path': str(source),
            'target_path': str(target),
            'action_type': 'move'
        }

        executor = MigrationExecutor(temp_db)
        executor._execute_move(action)

        assert not source.exists()
        assert target.exists()
        assert target.read_text() == "content"

    def test_execute_move_creates_target_directory(self, temp_db, temp_dir):
        """Move should create target directory if needed."""
        source = temp_dir / "file.txt"
        source.write_text("data")

        target = temp_dir / "new" / "nested" / "dir" / "file.txt"

        action = {
            'action_id': 'act-1',
            'source_path': str(source),
            'target_path': str(target)
        }

        executor = MigrationExecutor(temp_db)
        executor._execute_move(action)

        assert target.exists()

    def test_execute_move_handles_conflict(self, temp_db, temp_dir):
        """Move should handle target name conflicts."""
        source = temp_dir / "source.txt"
        source.write_text("source content")

        target = temp_dir / "target.txt"
        target.write_text("existing content")

        action = {
            'action_id': 'act-1',
            'source_path': str(source),
            'target_path': str(target)
        }

        executor = MigrationExecutor(temp_db)
        executor._execute_move(action)

        # Original should be gone
        assert not source.exists()

        # Should have created target_1.txt
        assert (temp_dir / "target_1.txt").exists()

    def test_execute_move_nonexistent_source(self, temp_db, temp_dir):
        """Move should fail for nonexistent source."""
        action = {
            'action_id': 'act-1',
            'source_path': str(temp_dir / "nonexistent.txt"),
            'target_path': str(temp_dir / "target.txt")
        }

        executor = MigrationExecutor(temp_db)

        with pytest.raises(FileNotFoundError):
            executor._execute_move(action)


class TestCopyAction:
    """Test file copy action execution."""

    def test_execute_copy_action(self, temp_db, temp_dir):
        """Should copy file to target location."""
        source = temp_dir / "source.txt"
        source.write_text("copy me")

        target = temp_dir / "copy.txt"

        action = {
            'action_id': 'act-1',
            'source_path': str(source),
            'target_path': str(target)
        }

        executor = MigrationExecutor(temp_db)
        executor._execute_copy(action)

        assert source.exists()  # Original still exists
        assert target.exists()
        assert target.read_text() == "copy me"


class TestDeleteAction:
    """Test file delete action execution (moves to trash)."""

    def test_execute_delete_moves_to_trash(self, temp_db, temp_dir):
        """Delete should move file to trash, not permanently delete."""
        # Change to temp_dir for trash creation
        original_dir = os.getcwd()
        os.chdir(temp_dir)

        try:
            file_to_delete = temp_dir / "delete_me.txt"
            file_to_delete.write_text("delete this")

            action = {
                'action_id': 'act-1',
                'source_path': str(file_to_delete)
            }

            executor = MigrationExecutor(temp_db)
            executor._execute_delete(action)

            assert not file_to_delete.exists()

            # Should be in Quarantine/Trash
            trash_dir = Path("Quarantine") / "Trash"
            assert trash_dir.exists()
        finally:
            os.chdir(original_dir)

    def test_execute_delete_nonexistent_file(self, temp_db, temp_dir):
        """Delete should handle nonexistent files gracefully."""
        action = {
            'action_id': 'act-1',
            'source_path': str(temp_dir / "nonexistent.txt")
        }

        executor = MigrationExecutor(temp_db)
        # Should not raise an exception
        executor._execute_delete(action)


class TestConflictResolution:
    """Test file naming conflict resolution."""

    def test_resolve_conflict_increments_counter(self, temp_db, temp_dir):
        """Conflict resolution should add incrementing suffix."""
        # Create existing files
        (temp_dir / "file.txt").write_text("1")
        (temp_dir / "file_1.txt").write_text("2")
        (temp_dir / "file_2.txt").write_text("3")

        executor = MigrationExecutor(temp_db)
        resolved = executor._resolve_conflict(temp_dir / "file.txt")

        assert resolved.name == "file_3.txt"

    def test_resolve_conflict_preserves_extension(self, temp_db, temp_dir):
        """Conflict resolution should preserve file extension."""
        (temp_dir / "doc.pdf").write_bytes(b"pdf")

        executor = MigrationExecutor(temp_db)
        resolved = executor._resolve_conflict(temp_dir / "doc.pdf")

        assert resolved.suffix == ".pdf"
        assert resolved.name == "doc_1.pdf"


class TestRollback:
    """Test migration rollback functionality."""

    def test_rollback_restores_moved_files(self, temp_db, temp_dir, checkpoint_dir):
        """Rollback should restore files to original locations."""
        # Create checkpoint data
        source = temp_dir / "original.txt"
        target = temp_dir / "moved.txt"

        source.write_text("original")

        # Simulate move
        shutil.move(str(source), str(target))

        # Create checkpoint
        checkpoint_file = checkpoint_dir / "test_plan.json"
        checkpoint_data = {
            'plan_id': 'test_plan',
            'created_at': datetime.now().isoformat(),
            'actions': [
                {
                    'action_id': 'act-1',
                    'source': str(source),
                    'target': str(target),
                    'type': 'move'
                }
            ]
        }

        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f)

        executor = MigrationExecutor(temp_db)
        executor._rollback(checkpoint_file)

        assert source.exists()
        assert not target.exists()

    def test_rollback_handles_missing_checkpoint(self, temp_db, temp_dir):
        """Rollback should handle missing checkpoint gracefully."""
        executor = MigrationExecutor(temp_db)

        # Should not raise exception
        executor._rollback(temp_dir / "nonexistent_checkpoint.json")


class TestAddAction:
    """Test action insertion."""

    def test_add_action_stores_in_database(self, temp_db, migrator_config, structure_config):
        """Add action should insert record into database."""
        session_id = temp_db.create_session(['/test'], {})

        planner = MigrationPlanner(temp_db, migrator_config)
        plan_id = planner.create_plan(session_id, structure_config)

        planner._add_action(
            plan_id=plan_id,
            source_path='/test/source.txt',
            target_path='/test/target.txt',
            action_type='move',
            rule_id='test_rule',
            reason='Test reason',
            file_size=1000
        )

        cursor = temp_db.conn.cursor()
        cursor.execute("SELECT * FROM migration_actions WHERE plan_id = ?", (plan_id,))
        actions = cursor.fetchall()

        assert len(actions) >= 1
        assert any(a['rule_id'] == 'test_rule' for a in actions)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

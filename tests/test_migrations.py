import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sdd_hermes import SDDService
from sdd_hermes.core import Ledger, ProjectPaths, SCHEMA_VERSION, SDDError


FIXTURE = Path(__file__).parent / 'fixtures/ledger-v5.sql'


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.paths = ProjectPaths(self.root)
        self.paths.prepare()
        with closing(sqlite3.connect(self.paths.database)) as db, db:
            db.executescript(FIXTURE.read_text().replace('__REPOSITORY_ROOT__', str(self.root).replace("'", "''")))

    def snapshot(self, path=None):
        with closing(sqlite3.connect(path or self.paths.database)) as db:
            return '\n'.join(db.iterdump())

    def test_populated_v5_migration_preserves_records_and_native_references(self):
        before = self.snapshot()
        service = SDDService(self.root)
        status = service.status()
        self.assertEqual(status['project']['root'], str(self.root))
        self.assertEqual(status['tasks'][0]['native_task_id'], 'native-v5')
        self.assertEqual(status['capacity'][0]['operation_id'], 'reservation-v5')
        self.assertEqual(status['ownership'][0]['path'], 'app.py')
        with service.ledger._connect() as db:
            self.assertEqual(db.execute("SELECT value FROM metadata WHERE key = 'schema_version'").fetchone()[0], str(SCHEMA_VERSION))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM request_repositories').fetchone()[0], 2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM active_requests').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT summary FROM attempts').fetchone()[0], 'historical attempt')
            self.assertEqual(db.execute('SELECT output FROM evidence').fetchone()[0], 'historical evidence')
        backups = list(self.paths.runtime.glob('ledger.pre-v6-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.snapshot(backups[0]), before)
        after = self.snapshot()
        SDDService(self.root)
        self.assertEqual(self.snapshot(), after)
        self.assertEqual(len(list(self.paths.runtime.glob('ledger.pre-v6-*.sqlite3'))), 1)

    def test_migration_failure_rolls_back_schema_and_preserves_backup(self):
        before = self.snapshot()
        with patch.object(Ledger, '_migrate_request_associations', side_effect=SDDError('injected interruption')):
            with self.assertRaisesRegex(SDDError, 'injected'):
                SDDService(self.root)
        self.assertEqual(self.snapshot(), before)
        backup = next(self.paths.runtime.glob('ledger.pre-v6-*.sqlite3'))
        self.assertEqual(self.snapshot(backup), before)
        self.assertTrue(SDDService(self.root).status()['initialized'])

    def test_future_schema_refused_before_database_or_files_change(self):
        with closing(sqlite3.connect(self.paths.database)) as db, db:
            db.execute("UPDATE metadata SET value = '999' WHERE key = 'schema_version'")
        before = self.snapshot()
        files = {p.relative_to(self.root) for p in self.root.rglob('*')}
        with self.assertRaisesRegex(SDDError, 'newer plugin'):
            SDDService(self.root)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({p.relative_to(self.root) for p in self.root.rglob('*')}, files)

    def test_inconsistent_archived_root_blocks_without_partial_migration(self):
        with closing(sqlite3.connect(self.paths.database)) as db, db:
            db.execute("UPDATE projects SET stage = 'running' WHERE stage = 'closed'")
        before = self.snapshot()
        with self.assertRaisesRegex(SDDError, 'ambiguous archived'):
            SDDService(self.root)
        self.assertEqual(self.snapshot(), before)

    def test_migrated_active_request_replays_after_historical_request(self):
        service = SDDService(self.root)
        project = service.ledger.project()
        replay = service.initialize('Fix active regression', 'bugfix')
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['project']['project_id'], project['project_id'])
        self.assertEqual(replay['project']['stage'], project['stage'])
        self.assertEqual(replay['project']['board_slug'], 'sdd-active')

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.package_release import build


class PackageReleaseTests(unittest.TestCase):
    def test_rebuild_excludes_outputs_and_local_workspace_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'plugin.yaml').write_text('name: test\n')
            for name in ('.env', '.codex/session', '.agents/session', 'dist/old.tar.gz'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('local data')
            output = root / 'artifact/plugin.tar.gz'
            first = build(root, output)
            second = build(root, output)
            self.assertEqual(first['files'], ['plugin.yaml'])
            self.assertEqual(first['files'], second['files'])
            self.assertEqual(first['sha256'], second['sha256'])
            with tarfile.open(output) as archive:
                self.assertEqual(archive.getnames(), ['plugin.yaml'])

    def test_archive_is_independent_of_time_filename_and_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'source'
            root.mkdir()
            source = root / 'plugin.yaml'
            source.write_text('name: test\n')
            with patch('time.time', return_value=1000):
                first = build(root, Path(directory) / 'first.tar.gz')
            source.chmod(0o777)
            with patch('time.time', return_value=2000):
                second = build(root, Path(directory) / 'second.tar.gz')
            self.assertEqual(first['sha256'], second['sha256'])
            with tarfile.open(Path(directory) / 'second.tar.gz') as archive:
                info = archive.getmembers()[0]
                self.assertEqual((info.uid, info.gid, info.uname, info.gname, info.mtime, info.mode),
                                 (0, 0, '', '', 0, 0o644))

    def test_output_inside_included_directory_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('test')
            output = root / 'docs/release.tar.gz'
            build(root, output)
            self.assertEqual(build(root, output)['files'], ['README.md'])

    def test_symlinked_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'source'
            root.mkdir()
            outside = Path(directory) / 'private'
            outside.write_text('private')
            try:
                (root / 'README.md').symlink_to(outside)
            except OSError:
                self.skipTest('symlink creation unavailable')
            with self.assertRaises(ValueError):
                build(root, Path(directory) / 'plugin.tar.gz')

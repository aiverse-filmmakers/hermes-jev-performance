import hashlib
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

from scripts import build_release
from scripts.build_release import build, verify

ROOT = pathlib.Path(__file__).resolve().parents[1]
PREFIX = 'hermes-jev-performance/'


class ReleasePackageTests(unittest.TestCase):
    def test_release_packages_are_small_scoped_versioned_and_extractable(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp)
            metadata = build(output)
            verify(metadata, output)
            packages = metadata['packages']
            self.assertLess(packages['server']['bytes'], 200_000)
            self.assertLess(packages['desktop']['bytes'], 30_000)
            for kind, entry in packages.items():
                with zipfile.ZipFile(output / entry['path']) as archive:
                    names = set(archive.namelist())
                    self.assertTrue(all(n.startswith(PREFIX) and '..' not in n.split('/') for n in names))
                    archive.extractall(output / kind)
                    folder = output / kind / 'hermes-jev-performance'
                    self.assertTrue((folder / 'README.md').is_file())
                    if kind == 'server':
                        self.assertIn(PREFIX + 'jevperf/plugin.py', names)
                        self.assertIn(PREFIX + 'dashboard/server-only.js', names)
                        self.assertFalse(any('/dist/' in n or '/desktop/' in n or '/benchmarks/' in n for n in names))
                        self.assertEqual((folder / 'plugin.yaml').read_bytes(), (ROOT / 'agent/plugin.yaml').read_bytes())
                        self.assertEqual((folder / 'after-install.md').read_bytes(), (ROOT / 'agent/after-install.md').read_bytes())
                    elif kind == 'desktop':
                        self.assertEqual(names, {PREFIX + n for n in ('LICENSE', 'README.md', 'plugin.js')})
                    else:
                        self.assertIn(PREFIX + 'desktop/plugin.js', names)
                        self.assertIn(PREFIX + 'docs/STATUS.md', names)
                package = output / entry['path']
                self.assertEqual(hashlib.sha256(package.read_bytes()).hexdigest(), entry['sha256'])
                self.assertTrue(package.with_suffix(package.suffix + '.sha256').is_file())
                self.assertTrue(package.with_suffix(package.suffix + '.files.txt').is_file())

    def test_zip_is_identical_across_checkout_times_and_permissions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            selected = build_release._files_for('desktop')
            for source, _ in selected:
                target = root / source.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            with mock.patch.object(build_release, 'ROOT', root):
                files = [source for source, _ in build_release._files_for('desktop')]
                for source in files:
                    os.utime(source, (1700000000, 1700000000))
                    source.chmod(0o600)
                first = build_release._write_zip('desktop', root / 'a.zip')[1]
                for source in files:
                    os.utime(source, (1700000400, 1700000400))
                    source.chmod(0o755)
                second = build_release._write_zip('desktop', root / 'b.zip')[1]
            self.assertEqual(first, second)

    def test_verifier_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            metadata = build(root)
            target = root / metadata['packages']['desktop']['path']
            with zipfile.ZipFile(target, 'a') as archive:
                archive.writestr('../escape', 'bad')
            with self.assertRaises(ValueError):
                verify(metadata, root)

    def test_extracted_entry_points_load_without_repository_import_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp)
            metadata = build(output)
            for kind in ('server', 'combined'):
                with self.subTest(kind=kind):
                    location = output / kind
                    with zipfile.ZipFile(output / metadata['packages'][kind]['path']) as archive:
                        archive.extractall(location)
                    environment = dict(os.environ, HERMES_HOME=str(output / ('profile-' + kind)), PYTHONDONTWRITEBYTECODE='1')
                    environment.pop('PYTHONPATH', None)
                    process = subprocess.run([sys.executable, '-I', str(ROOT / 'tests/package_contract_runner.py'), str(location / 'hermes-jev-performance')], cwd=location, env=environment, text=True, capture_output=True, timeout=20)
                    self.assertEqual(process.returncode, 0, process.stderr)
                    self.assertIn('isolated package PASS', process.stdout)


if __name__ == '__main__':
    unittest.main()

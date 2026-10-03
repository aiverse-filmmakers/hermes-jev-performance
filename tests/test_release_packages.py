import pathlib
import tempfile
import unittest
import zipfile

from scripts.build_release import build, verify


class ReleasePackageTests(unittest.TestCase):
    def test_release_packages_are_small_scoped_and_versioned(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp)
            metadata = build(output)
            verify(metadata, output)
            packages = metadata["packages"]
            server = packages["server"]
            desktop = packages["desktop"]
            combined = packages["combined"]

            self.assertLess(server["bytes"], 200_000)
            self.assertLess(desktop["bytes"], 30_000)
            self.assertGreater(combined["bytes"], desktop["bytes"])

            with zipfile.ZipFile(output / server["path"]) as archive:
                names = set(archive.namelist())
                self.assertIn("jevperf/plugin.py", names)
                self.assertIn("dashboard/server-only.js", names)
                self.assertNotIn("desktop/plugin.js", names)
                self.assertFalse(any("dist/" in name for name in names))

            with zipfile.ZipFile(output / desktop["path"]) as archive:
                self.assertEqual(set(archive.namelist()), {"LICENSE", "README.md", "plugin.js"})

            with zipfile.ZipFile(output / combined["path"]) as archive:
                self.assertIn("desktop/plugin.js", archive.namelist())
                self.assertIn("dashboard/dist/index.js", archive.namelist())

            for entry in packages.values():
                package = output / entry["path"]
                self.assertTrue(package.with_suffix(package.suffix + ".sha256").is_file())
                self.assertTrue(package.with_suffix(package.suffix + ".files.txt").is_file())


if __name__ == "__main__":
    unittest.main()

import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from jevperf.doctor import render_doctor, run_doctor
from jevperf.store import MetricsStore, inspect_database, repair_corrupt_database
from tests.fakes import FakeContext


ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def make_db_path(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name) / "metrics.sqlite3"

    def secret_reader(self, name):
        if name == "OPENROUTER_JEV_API_TOKEN":
            return "SECRET_VALUE_MUST_NEVER_PRINT"
        return ""

    def test_doctor_is_network_free_and_does_not_print_secret(self):
        path = self.make_db_path()
        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError("doctor must not use network"),
        ):
            report = run_doctor(
                FakeContext(),
                plugin_root=ROOT,
                db_path=path,
                secret_reader=self.secret_reader,
            )
        rendered = render_doctor(report)
        serialized = json.dumps(report)
        self.assertEqual(report["network_calls"], 0)
        self.assertNotIn("SECRET_VALUE_MUST_NEVER_PRINT", rendered)
        self.assertNotIn("SECRET_VALUE_MUST_NEVER_PRINT", serialized)
        self.assertIn("OPENROUTER_JEV_API_TOKEN", rendered)

    def test_missing_credential_is_warning_not_secret_failure(self):
        report = run_doctor(
            FakeContext(),
            plugin_root=ROOT,
            db_path=self.make_db_path(),
            secret_reader=lambda name: "",
        )
        check = next(
            row for row in report["checks"]
            if row["name"] == "openrouter_credential"
        )
        self.assertEqual(check["status"], "warn")
        self.assertIn("fail open", check["detail"])

    def test_version_below_declared_floor_is_failure(self):
        with mock.patch(
            "jevperf.compatibility.detect_hermes_version",
            return_value="0.21.4",
        ), mock.patch(
            "jevperf.doctor.detect_hermes_version",
            return_value="0.21.4",
        ):
            report = run_doctor(
                FakeContext(),
                plugin_root=ROOT,
                db_path=self.make_db_path(),
                secret_reader=self.secret_reader,
            )
        by_name = {row["name"]: row for row in report["checks"]}
        self.assertEqual(report["overall"], "fail")
        self.assertEqual(by_name["hermes_plugin_api"]["status"], "fail")
        self.assertEqual(by_name["hermes_version"]["status"], "fail")
        self.assertIn("below required 0.21.5", by_name["hermes_version"]["detail"])

    def test_unparseable_version_is_warning_not_false_pass(self):
        with mock.patch(
            "jevperf.compatibility.detect_hermes_version",
            return_value="development",
        ), mock.patch(
            "jevperf.doctor.detect_hermes_version",
            return_value="development",
        ):
            report = run_doctor(
                FakeContext(),
                plugin_root=ROOT,
                db_path=self.make_db_path(),
                secret_reader=self.secret_reader,
            )
        check = next(row for row in report["checks"] if row["name"] == "hermes_version")
        self.assertEqual(check["status"], "warn")
        self.assertIn("unable to parse", check["detail"])

    def test_corrupt_database_is_detected_without_automatic_mutation(self):
        path = self.make_db_path()
        path.write_bytes(b"not a sqlite database")
        before = path.read_bytes()
        report = run_doctor(
            FakeContext(),
            plugin_root=ROOT,
            db_path=path,
            secret_reader=self.secret_reader,
        )
        check = next(
            row for row in report["checks"]
            if row["name"] == "telemetry_database"
        )
        self.assertEqual(check["status"], "fail")
        self.assertEqual(path.read_bytes(), before)

    def test_explicit_corrupt_database_repair_quarantines_main_wal_and_shm(self):
        path = self.make_db_path()
        path.write_bytes(b"not a sqlite database")
        wal = Path(str(path) + "-wal")
        shm = Path(str(path) + "-shm")
        wal.write_bytes(b"old wal bytes")
        shm.write_bytes(b"old shm bytes")

        report = run_doctor(
            FakeContext(),
            plugin_root=ROOT,
            db_path=path,
            secret_reader=self.secret_reader,
            repair_db=True,
        )
        check = next(
            row for row in report["checks"]
            if row["name"] == "telemetry_database"
        )
        self.assertEqual(check["status"], "pass")
        self.assertEqual(inspect_database(path)["state"], "ready")

        main_backups = list(path.parent.glob("metrics.sqlite3.corrupt-*"))
        wal_backups = list(path.parent.glob("metrics.sqlite3-wal.corrupt-*"))
        shm_backups = list(path.parent.glob("metrics.sqlite3-shm.corrupt-*"))
        self.assertEqual(len(main_backups), 1)
        self.assertEqual(len(wal_backups), 1)
        self.assertEqual(len(shm_backups), 1)
        self.assertEqual(main_backups[0].read_bytes(), b"not a sqlite database")
        self.assertEqual(wal_backups[0].read_bytes(), b"old wal bytes")
        self.assertEqual(shm_backups[0].read_bytes(), b"old shm bytes")

    def test_repair_function_does_not_replace_healthy_database(self):
        path = self.make_db_path()
        MetricsStore(path).initialize()
        result = repair_corrupt_database(path)
        self.assertFalse(result["repaired"])
        self.assertEqual(result["reason"], "database_is_healthy")
        self.assertEqual(list(path.parent.glob("*.corrupt-*")), [])

    def test_dashboard_and_fixture_assets_are_checked(self):
        report = run_doctor(
            FakeContext(),
            plugin_root=ROOT,
            db_path=self.make_db_path(),
            secret_reader=self.secret_reader,
        )
        by_name = {row["name"]: row for row in report["checks"]}
        self.assertEqual(by_name["dashboard_assets"]["status"], "pass")
        self.assertEqual(by_name["benchmark_fixtures"]["status"], "pass")
        self.assertEqual(by_name["plugin_manifest"]["status"], "pass")


if __name__ == "__main__":
    unittest.main()

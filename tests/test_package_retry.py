import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PROJECT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, PROJECT / "system" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


maintenance = load("maintenance")
packages = load("update_packages")


class PackageRetryTests(unittest.TestCase):
    def test_retry_preserves_signatures_and_custom_repository(self):
        source = "[options]\nSigLevel = Required DatabaseOptional\n[core]\nInclude = /etc/pacman.d/mirrorlist\n[custom]\nServer = https://example.org/$arch\n"
        result = packages.mirror_config(source)
        self.assertIn("SigLevel = Required DatabaseOptional", result)
        self.assertIn("Server = https://example.org/$arch", result)
        self.assertIn("Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch", result)

    def test_custom_configuration_without_standard_mirror_is_not_rewritten(self):
        with self.assertRaises(RuntimeError):
            packages.mirror_config("[core]\nServer = https://custom.invalid/$arch\n")

    def test_unrelated_failure_never_retries_or_changes_configuration(self):
        with patch.object(packages, "run_upgrade", return_value=(1, False)) as run, \
                patch.object(packages.Path, "read_text") as read:
            with self.assertRaises(RuntimeError):
                packages.upgrade()
            run.assert_called_once_with()
            read.assert_not_called()

    def test_signature_failure_retries_once_with_isolated_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            def run(extra=()):
                if not extra:
                    return 1, True
                self.assertIn("--cachedir", extra)
                self.assertTrue(Path(extra[extra.index("--config") + 1]).is_file())
                return 1, True
            real_temp = tempfile.TemporaryDirectory
            with patch.object(packages, "run_upgrade", side_effect=run) as runner, \
                    patch.object(packages.Path, "read_text", return_value="[core]\nInclude = /etc/pacman.d/mirrorlist\n"), \
                    patch.object(packages.tempfile, "TemporaryDirectory", side_effect=lambda **kw: real_temp(dir=directory)):
                with self.assertRaisesRegex(RuntimeError, "neue Download"):
                    packages.upgrade()
                self.assertEqual(runner.call_count, 2)
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()

"""Exercise update migration and the SSH setup without changing the host."""
import importlib.util
import json
from pathlib import Path
import shutil
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


ssh = load("configure_ssh")
diagnose = load("diagnose_firefox")
update = load("update_custom")


class SSHAccessTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "opt/saar-fighters"
        shutil.copytree(PROJECT / "system", self.project / "system")
        marker = self.root / "var/lib/saar-base-ready"
        marker.parent.mkdir(parents=True)
        marker.touch()
        self.calls = []

    def command(self, args):
        self.calls.append(args)
        if args[:2] == ["ssh-keygen", "-q"]:
            key = Path(args[-1])
            key.write_text("test-only-host-key")
            Path(str(key) + ".pub").write_text("test-only-public-key")
        return subprocess.CompletedProcess(args, 0, "[]" if args[0] == "ip" else "", "")

    def test_setup_is_immediate_idempotent_and_keeps_host_identity(self):
        self.assertTrue(ssh.configure(self.root, self.command))
        key = self.root / "etc/saar-fighters/ssh/host_ed25519"
        key.write_text("existing device identity")
        self.calls.clear()
        self.assertTrue(ssh.configure(self.root, self.command))
        self.assertEqual(key.read_text(), "existing device identity")
        self.assertFalse(any(c[:2] == ["ssh-keygen", "-q"] for c in self.calls))
        self.assertIn(["systemctl", "enable", "--now", ssh.SERVICE], self.calls)
        self.assertNotIn(["systemctl", "reload", ssh.SERVICE], self.calls)
        self.assertEqual((key.parent / "authorized_keys").read_text(),
                         ssh.public_key((PROJECT / "system/ssh/support_ed25519.pub").read_text()))

    def test_live_environment_never_enables_ssh(self):
        (self.root / "etc").mkdir()
        (self.root / "etc/saar-live").touch()
        self.assertFalse(ssh.configure(self.root, self.command))
        self.assertEqual(self.calls, [])

    def test_explicit_disable_survives_every_update(self):
        directory = self.root / "etc/saar-fighters/ssh"
        directory.mkdir(parents=True)
        (directory / "disabled").touch()
        self.assertFalse(ssh.configure(self.root, self.command))
        self.assertEqual(self.calls, [["systemctl", "disable", "--now", ssh.SERVICE]])

    def test_invalid_config_is_rejected_before_replacing_working_files(self):
        ssh.configure(self.root, self.command)
        authorized = self.root / "etc/saar-fighters/ssh/authorized_keys"
        authorized.write_text("previous trusted key")
        self.calls.clear()
        def reject(args):
            if args[0] == "sshd":
                raise subprocess.CalledProcessError(1, args)
            return self.command(args)
        with self.assertRaises(subprocess.CalledProcessError):
            ssh.configure(self.root, reject)
        self.assertEqual(authorized.read_text(), "previous trusted key")
        self.assertFalse(any(c[0] == "systemctl" for c in self.calls))
        self.assertEqual(list(self.root.rglob(".saar-ssh-*")), [])

    def test_partial_file_failure_restores_previous_keys_and_config(self):
        ssh.configure(self.root, self.command)
        authorized = self.root / "etc/saar-fighters/ssh/authorized_keys"
        authorized.write_text("previous key")
        config = authorized.parent / "sshd_config"
        config.write_text("previous config")
        replace = ssh.os.replace
        def fail(source, destination):
            if destination == config:
                raise OSError("disk failure")
            return replace(source, destination)
        with patch.object(ssh.os, "replace", fail), self.assertRaises(OSError):
            ssh.configure(self.root, self.command)
        self.assertEqual(authorized.read_text(), "previous key")
        self.assertEqual(config.read_text(), "previous config")

    def test_failure_to_start_service_does_not_report_success(self):
        def fail(args):
            if args[:2] == ["systemctl", "enable"]:
                raise subprocess.CalledProcessError(1, args)
            return self.command(args)
        with self.assertRaises(subprocess.CalledProcessError):
            ssh.configure(self.root, fail)

    def test_keys_cannot_inject_authorized_keys_options(self):
        key = (PROJECT / "system/ssh/support_ed25519.pub").read_text()
        for value in ("command=bad " + key, key + key, "ssh-ed25519 !!!", "ssh-ed25519 YWJj"):
            with self.assertRaises(ValueError):
                ssh.public_key(value)

    def test_only_rfc1918_addresses_are_advertised(self):
        data = [{"addr_info": [{"local": a} for a in
                 ("192.168.1.4", "10.1.2.3", "172.31.1.3", "172.32.1.3", "8.8.8.8",
                  "127.0.0.1", "169.254.1.1", "::1", "not-an-ip")]}]
        self.assertEqual(ssh.local_addresses(data), ["10.1.2.3", "172.31.1.3", "192.168.1.4"])

    def test_crash_report_omits_urls_and_arbitrary_sensitive_fields(self):
        pending = self.root / "pending"
        pending.mkdir()
        (pending / "test.extra").write_text(json.dumps({"Version": "158", "OOMAllocationSize": "4096",
            "URL": "https://private.invalid", "Email": "private@example.invalid", "StackTraces": "private"}))
        self.assertEqual(diagnose.crash_metadata(pending), [{"Version": "158", "OOMAllocationSize": "4096"}])

    def test_update_can_install_ssh_after_already_current_revision(self):
        # Existing helpers do not run newly downloaded migration code. The first
        # update installs the new shell/helper; the second invokes configure_ssh
        # even when install_checkout correctly skips the unchanged revision.
        for folder in ("app", "installer"):
            (self.project / folder).mkdir()
        checkout = self.root / "checkout"
        for folder in ("app", "system", "installer"):
            shutil.copytree(PROJECT / folder, checkout / folder)
        self.assertTrue(update.install_checkout(checkout, "a" * 40, self.root))
        self.assertFalse(update.install_checkout(checkout, "a" * 40, self.root))
        self.assertTrue(ssh.configure(self.root, self.command))
        helper = (self.root / "usr/local/libexec/saar-update").read_text()
        self.assertLess(helper.index("saar-update-custom.py"), helper.index("configure_ssh.py"))


if __name__ == "__main__":
    unittest.main()

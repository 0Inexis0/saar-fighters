#!/usr/bin/env python3
"""Real OpenSSH acceptance test. Run as root only on an ephemeral CI runner."""
import importlib.util
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

PROJECT = Path(__file__).resolve().parents[1]


def run(*args, check=True, **kwargs):
    return subprocess.run(args, check=check, capture_output=True, text=True, timeout=20, **kwargs)


def main():
    if os.geteuid() != 0 or os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("Only run as root on the disposable GitHub Actions runner.")
    username = "saar-ssh-test-" + secrets.token_hex(3)
    server = None
    created = False
    spec = importlib.util.spec_from_file_location("ssh_setup", PROJECT / "system/configure_ssh.py")
    setup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(setup)
    # StrictModes checks every ancestor of AuthorizedKeysFile, so a world-writable
    # /tmp parent is intentionally unsuitable even for this temporary test.
    with tempfile.TemporaryDirectory(prefix="saar-ssh-test-", dir="/var/lib") as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        source = root / "opt/saar-fighters/system"
        shutil.copytree(PROJECT / "system", source)
        marker = root / "var/lib/saar-base-ready"
        marker.parent.mkdir(parents=True)
        marker.touch()
        client_key = root / "client"
        wrong_key = root / "wrong"
        for key in (client_key, wrong_key):
            run("ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key))
        shutil.copyfile(str(client_key) + ".pub", source / "ssh/support_ed25519.pub")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        config = (source / "ssh/sshd_config").read_text()
        config = config.replace("Port 2222", f"Port {port}").replace("wartung@", username + "@")
        config = config.replace("/etc/saar-fighters/ssh/", str(root / "etc/saar-fighters/ssh") + "/")
        config = config.replace("/run/saar-sshd.pid", str(root / "server.pid"))
        (source / "ssh/sshd_config").write_text(config)
        sshd = shutil.which("sshd")
        Path("/run/sshd").mkdir(exist_ok=True)
        try:
            run("useradd", "--create-home", "--shell", "/bin/sh", username)
            created = True
            run("chpasswd", input=username + ":" + secrets.token_urlsafe(32) + "\n")
            def command(args):
                if args[0] == "systemctl":
                    return subprocess.CompletedProcess(args, 0, "", "")
                if args == ["id", "wartung"]:
                    return run("id", username)
                if args[0] == "sshd":
                    return run(sshd, *args[1:])
                return run(*args)
            assert setup.configure(root, command)
            assert setup.configure(root, command)
            installed = root / "etc/saar-fighters/ssh/sshd_config"
            effective = run(sshd, "-T", "-f", str(installed)).stdout
            for setting in ("passwordauthentication no", "kbdinteractiveauthentication no",
                            "permitrootlogin no", "authenticationmethods publickey",
                            "disableforwarding yes", "addressfamily inet"):
                assert setting in effective, setting
            with (root / "server.log").open("w+") as log:
                server = subprocess.Popen([sshd, "-D", "-e", "-f", str(installed)], stdout=log, stderr=log)
                for _ in range(50):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise AssertionError("OpenSSH did not start")
                options = ["ssh", "-p", str(port), "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
                           "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=accept-new",
                           "-o", f"UserKnownHostsFile={root / 'known_hosts'}"]
                success = run(*options, "-i", str(client_key), username + "@127.0.0.1", "id -un")
                assert success.stdout.strip() == username, success.stdout
                for key, user, extra in ((wrong_key, username, []), (client_key, "root", []),
                                         (client_key, username, ["-b", "127.0.0.2"]),
                                         (client_key, username, ["-o", "PubkeyAuthentication=no"]),
                                         (client_key, username, ["-o", "ExitOnForwardFailure=yes", "-R", "0:127.0.0.1:9"])):
                    result = run(*options, "-i", str(key), *extra, user + "@127.0.0.1", "true", check=False)
                    assert result.returncode != 0, f"Access unexpectedly allowed: {user}, {extra}"
                fingerprint = run("ssh-keygen", "-lf", str(root / "etc/saar-fighters/ssh/host_ed25519.pub")).stdout
                assert "ED25519" in fingerprint
            # Actually execute the narrow sudo rule with a harmless temporary
            # helper and confirm that argv injection is rejected by sudo.
            helper = root / "usr/local/libexec/saar-diagnose-firefox"
            helper.write_text("#!/bin/sh\nprintf 'diagnostic-ok\\n'\n")
            helper.chmod(0o755)
            sudoers = Path("/etc/sudoers.d") / username
            try:
                rule = setup.SUDOERS.replace("wartung ", username + " ").replace(
                    "/usr/local/libexec/saar-diagnose-firefox", str(helper))
                sudoers.write_text(rule)
                sudoers.chmod(0o440)
                run("visudo", "-cf", str(sudoers))
                assert run("runuser", "-u", username, "--", "sudo", "-n", str(helper)).stdout.strip() == "diagnostic-ok"
                assert run("runuser", "-u", username, "--", "sudo", "-n", str(helper), "extra", check=False).returncode != 0
                assert run("runuser", "-u", username, "--", "sudo", "-n", "/usr/bin/id", check=False).returncode != 0
            finally:
                sudoers.unlink(missing_ok=True)
            print("PASS: actual key login; wrong key, root, disallowed source, password-only and forwarding rejected; narrow sudo checked.")
        finally:
            if sys.exc_info()[0] is not None and (root / "server.log").exists():
                print((root / "server.log").read_text()[-12000:])
            if server is not None:
                server.terminate()
                server.wait(timeout=10)
            if created:
                run("userdel", "--remove", username, check=False)


if __name__ == "__main__":
    main()

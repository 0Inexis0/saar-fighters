#!/usr/bin/python -I
"""Fixed read-only Firefox report, callable through a narrowly scoped sudo rule."""
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

FIELDS = {"Version", "BuildID", "CrashTime", "ProcessType", "StartupTime", "OOMAllocationSize",
          "AvailablePhysicalMemory", "TotalPhysicalMemory", "AvailableSwapMemory",
          "GPUProcessLaunchCount", "AdapterVendorID", "AdapterDeviceID", "AdapterDriverVersion"}


def command(*args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20,
                                env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"})
        return {"code": result.returncode, "output": result.stdout[-24000:]}
    except (OSError, subprocess.SubprocessError) as error:
        return {"error": type(error).__name__}


def crash_metadata(directory):
    reports = []
    if not directory.is_dir() or directory.is_symlink():
        return reports
    for file in sorted(directory.glob("*.extra"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
        if file.is_symlink() or file.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            # Exclude URLs, session data, raw crash dumps and arbitrary annotations.
            reports.append({k: str(v)[:120] for k, v in data.items() if k in FIELDS})
        except (OSError, ValueError, AttributeError):
            continue
    return reports


def main():
    import pwd
    if sys.argv[1:] or os.geteuid() != 0:
        raise SystemExit("Aufruf ohne Argumente über sudo erforderlich.")
    report = {
        "packages": command("pacman", "-Q", "firefox", "mesa", "linux", "intel-ucode", "amd-ucode"),
        "memory": command("free", "-m"),
        "swap": command("swapon", "--show", "--bytes"),
        "graphics": command("lspci", "-nnk", "-d", "::03xx"),
        "kernel": command("uname", "-r"),
        "kernel_events": command("journalctl", "-k", "-b", "--no-pager", "-n", "80",
                                 "--grep=oom|Out of memory|Killed process|segfault|GPU HANG|GPU reset|Xid|amdgpu.*(fail|timeout)"),
        "previous_kernel_events": command("journalctl", "-k", "-b", "-1", "--no-pager", "-n", "40",
                                          "--grep=oom|Out of memory|Killed process|segfault|GPU HANG|GPU reset|Xid"),
    }
    crash_dir = Path("/home/saar/.mozilla/firefox/Crash Reports")
    # Resolve every parent as well, so the unprivileged user cannot redirect the
    # privileged reader into another account's files.
    if crash_dir.resolve() == crash_dir:
        report["crashes"] = crash_metadata(crash_dir / "pending")
    try:
        uid = pwd.getpwnam("saar").pw_uid
        report["playback"] = command("runuser", "-u", "saar", "--", "env",
            f"DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus", f"XDG_RUNTIME_DIR=/run/user/{uid}",
            "/usr/bin/python", "-I", "/opt/saar-fighters/system/playback_status.py")
    except KeyError:
        report["playback"] = {"error": "desktop user unavailable"}
    health = Path("/home/saar/.local/state/saar-fighters/app-health.jsonl")
    report["application_events"] = []
    if health.resolve() == health and health.is_file() and health.stat().st_size < 100000:
        for line in health.read_text(encoding="utf-8", errors="replace").splitlines()[-30:]:
            try:
                row = json.loads(line)
                # No arbitrary user-written strings may escape this privileged reader.
                if row.get("app") not in {"spotify", "web", "youtube", "club", "rocket", "files"}:
                    continue
                if row.get("event") not in {"start", "exit", "error"}:
                    continue
                safe = {"app": row["app"], "event": row["event"]}
                if isinstance(row.get("time"), str):
                    try:
                        safe["time"] = datetime.fromisoformat(row["time"]).isoformat()
                    except ValueError:
                        pass
                if isinstance(row.get("code"), int):
                    safe["code"] = row["code"]
                if row.get("category") in {"memory", "graphics", "audio"}:
                    safe["category"] = row["category"]
                report["application_events"].append(safe)
            except (ValueError, AttributeError, TypeError):
                continue
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

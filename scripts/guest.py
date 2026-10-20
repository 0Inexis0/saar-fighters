#!/usr/bin/env python3
"""Execute a command in the dedicated test VM through its QEMU agent."""
import base64
import json
import subprocess
import sys
import time

DOMAIN = "saar-fighters-os"


def call(data):
    result = subprocess.run(["virsh", "-c", "qemu:///session", "qemu-agent-command",
                             DOMAIN, json.dumps(data)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)["return"]


if __name__ == "__main__":
    pid = call({"execute": "guest-exec", "arguments": {
        "path": "/bin/bash", "arg": ["-lc", sys.argv[1]], "capture-output": True}})["pid"]
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        result = call({"execute": "guest-exec-status", "arguments": {"pid": pid}})
        if result.get("exited"):
            for key in ("out-data", "err-data"):
                if key in result:
                    print(base64.b64decode(result[key]).decode(errors="replace"), end="")
            sys.exit(result.get("exitcode", 1))
        time.sleep(1)
    raise SystemExit("Guest command timed out; it may still be running.")

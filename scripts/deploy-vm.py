#!/usr/bin/env python3
"""Copy the project to the dedicated VM; no host-side root operations."""
import base64
import io
import json
from pathlib import Path
import sys
import tarfile
import time

from guest import call

ROOT = Path(__file__).resolve().parents[1]
archive = io.BytesIO()
with tarfile.open(fileobj=archive, mode="w:gz") as tar:
    for folder in ("app", "system"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                tar.add(path, arcname=str(path.relative_to(ROOT)))
data = archive.getvalue()
handle = call({"execute": "guest-file-open", "arguments": {
    "path": "/root/saar-payload.tar.gz", "mode": "w"}})
try:
    for offset in range(0, len(data), 32768):
        chunk = data[offset:offset + 32768]
        result = call({"execute": "guest-file-write", "arguments": {
            "handle": handle, "buf-b64": base64.b64encode(chunk).decode()}})
        if result["count"] != len(chunk):
            raise RuntimeError("Short guest write")
finally:
    call({"execute": "guest-file-close", "arguments": {"handle": handle}})
pid = call({"execute": "guest-exec", "arguments": {
    "path": "/bin/bash", "arg": ["-lc", "mkdir -p /opt/saar-fighters && "
    "tar --no-same-owner -xzf /root/saar-payload.tar.gz -C /opt/saar-fighters && "
    "bash /opt/saar-fighters/system/install.sh"], "capture-output": True}})["pid"]
for _ in range(180):
    result = call({"execute": "guest-exec-status", "arguments": {"pid": pid}})
    if result.get("exited"):
        for key in ("out-data", "err-data"):
            if key in result:
                print(base64.b64decode(result[key]).decode(errors="replace"), end="")
        sys.exit(result.get("exitcode", 1))
    time.sleep(1)
raise SystemExit("Deployment timed out; inspect VM before retrying")

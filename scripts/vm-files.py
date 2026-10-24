#!/usr/bin/env python3
"""Transfer small build payloads through QGA. Select a Saar VM via SAAR_VM."""
import argparse
import base64
from pathlib import Path
from guest import call

parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=["put", "get"])
parser.add_argument("local", type=Path)
parser.add_argument("remote")
args = parser.parse_args()
handle = call({"execute": "guest-file-open", "arguments": {
    "path": args.remote, "mode": "w" if args.operation == "put" else "r"}})
try:
    with args.local.open("rb" if args.operation == "put" else "wb") as stream:
        if args.operation == "put":
            while data := stream.read(49152):
                result = call({"execute": "guest-file-write", "arguments": {
                    "handle": handle, "buf-b64": base64.b64encode(data).decode()}})
                if result["count"] != len(data):
                    raise RuntimeError("Short guest write")
        else:
            while True:
                result = call({"execute": "guest-file-read", "arguments": {"handle": handle, "count": 49152}})
                stream.write(base64.b64decode(result.get("buf-b64", "")))
                if result["eof"]:
                    break
finally:
    call({"execute": "guest-file-close", "arguments": {"handle": handle}})

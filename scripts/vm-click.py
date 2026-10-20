#!/usr/bin/env python3
"""Click a known coordinate in the dedicated test VM via its virtual tablet."""
import argparse
import json
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument("x", type=int)
parser.add_argument("y", type=int)
parser.add_argument("--size", default="1360x768", help="Current guest display size")
args = parser.parse_args()
w, h = map(int, args.size.split("x"))
if not (0 <= args.x < w and 0 <= args.y < h):
    raise SystemExit("Coordinate outside display")


def send(events):
    subprocess.run(["virsh", "-c", "qemu:///session", "qemu-monitor-command",
                    "saar-fighters-os", json.dumps({
                        "execute": "input-send-event", "arguments": {"events": events}})],
                   check=True, stdout=subprocess.DEVNULL)


send([{"type": "abs", "data": {"axis": "x", "value": round(args.x * 32767 / (w - 1))}},
      {"type": "abs", "data": {"axis": "y", "value": round(args.y * 32767 / (h - 1))}}])
time.sleep(.1)
send([{"type": "btn", "data": {"down": True, "button": "left"}}])
time.sleep(.12)
send([{"type": "btn", "data": {"down": False, "button": "left"}}])
print(f"Clicked ({args.x}, {args.y}) in saar-fighters-os")

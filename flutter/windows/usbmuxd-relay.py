#!/usr/bin/env python3
"""Expose Windows' Apple Mobile Device Service to WSL as a private usbmuxd socket.

    python3 flutter/windows/usbmuxd-relay.py [--socket PATH] [--node PATH]

Then, in another WSL shell:

    export USBMUXD_SOCKET_ADDRESS=UNIX:<socket path>
    xtool devices

Why: USB/IP passthrough (usbipd-win) stalls on large iPhone transfers, so the app
upload never starts. Apple's own Windows driver stack handles USB; this relay only
forwards bytes from a UNIX socket (mode 0600, owner only) to a Windows node.exe that
connects to 127.0.0.1:27015. Nothing listens on the network; payloads are not logged.
Stop with Ctrl+C.
"""
import argparse
import os
import signal
import socket
import subprocess
import threading
from pathlib import Path

here = Path(__file__).resolve().parent
lab = Path(os.environ.get("XTOOL_FLUTTER_LAB", Path.home() / "xtool-flutter-lab"))
parser = argparse.ArgumentParser()
parser.add_argument("--socket", type=Path, default=lab / "runtime" / "windows-usbmuxd.sock")
parser.add_argument("--node", default="/mnt/c/Program Files/nodejs/node.exe")
args = parser.parse_args()

if not Path(args.node).exists():
    raise SystemExit(f"Windows node.exe not found at {args.node}; install Node.js on Windows or pass --node")
bridge = subprocess.run(["wslpath", "-w", str(here / "usbmuxd-bridge.cjs")],
                        check=True, capture_output=True, text=True).stdout.strip()

endpoint = args.socket
endpoint.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
os.chmod(endpoint.parent, 0o700)
if endpoint.exists():
    raise SystemExit(f"{endpoint} already exists; is another relay running? Remove it if not.")

children = set()
lock = threading.Lock()
child_env = {k: v for k, v in os.environ.items()
             if k in {"WSL_INTEROP", "WSL_DISTRO_NAME", "PATH", "SystemRoot", "WINDIR", "USBMUXD_WINDOWS_PORT"}}


def relay(connection):
    child = subprocess.Popen([args.node, bridge], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, bufsize=0, env=child_env)
    with lock:
        children.add(child)

    def send():
        try:
            while data := connection.recv(65536):
                remaining = memoryview(data)
                while remaining:
                    written = os.write(child.stdin.fileno(), remaining)
                    remaining = remaining[written:]
        except (OSError, ValueError):
            pass
        finally:
            try:
                child.stdin.close()
            except OSError:
                pass

    sender = threading.Thread(target=send, daemon=True)
    sender.start()
    try:
        while data := os.read(child.stdout.fileno(), 65536):
            connection.sendall(data)
    except OSError:
        pass
    finally:
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        connection.close()
        if child.poll() is None:
            child.terminate()
        try:
            child.wait(timeout=3)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        sender.join(timeout=1)
        with lock:
            children.discard(child)


server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(str(endpoint))
os.chmod(endpoint, 0o600)
server.listen(16)
print(f"Relay ready: export USBMUXD_SOCKET_ADDRESS=UNIX:{endpoint}", flush=True)


def stop(*_):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, stop)
try:
    while True:
        connection, _ = server.accept()
        threading.Thread(target=relay, args=(connection,), daemon=True).start()
except KeyboardInterrupt:
    pass
finally:
    server.close()
    endpoint.unlink(missing_ok=True)
    with lock:
        for child in children:
            if child.poll() is None:
                child.terminate()
    print("Relay stopped", flush=True)

#!/usr/bin/env python3
"""Private Windows Apple Mobile Device Service relay for WSL.

python3 flutter/windows/usbmuxd-relay.py [--socket PATH] [--node PATH]

Use USBMUXD_SOCKET_ADDRESS=UNIX:<socket path> in another shell.
A custom socket's parent must already be private or be a new directory.
No payloads are logged. Stop with Ctrl+C.
"""
import argparse
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import threading


def prepare_socket_parent(endpoint):
    parent = endpoint.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    attributes = parent.stat()
    if attributes.st_uid != os.getuid() or stat.S_IMODE(attributes.st_mode) & 0o077:
        raise ValueError('Socket parent must be owned by this user with mode 0700; use a private directory.')
    if endpoint.exists() or endpoint.is_symlink():
        raise ValueError(f'{endpoint} already exists; check whether another relay is running.')


def relay(connection, node, bridge, child_env, children, lock):
    try:
        child = subprocess.Popen([node, bridge], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, bufsize=0, env=child_env)
    except OSError:
        # A failed Windows interop process must not leave the USB client blocked.
        connection.close()
        return
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


def main():
    here = Path(__file__).resolve().parent
    lab = Path(os.environ.get('XTOOL_FLUTTER_LAB', Path.home() / 'xtool-flutter-lab'))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, default=lab / 'runtime/windows-usbmuxd.sock')
    parser.add_argument('--node', default='/mnt/c/Program Files/nodejs/node.exe')
    args = parser.parse_args()
    if not Path(args.node).is_file():
        parser.exit(1, f'Windows node.exe not found at {args.node}; install Node.js or pass --node.\n')
    try:
        prepare_socket_parent(args.socket)
    except ValueError as error:
        parser.exit(1, f'{error}\n')
    bridge = subprocess.run(['wslpath', '-w', str(here / 'usbmuxd-bridge.cjs')],
                            check=True, capture_output=True, text=True).stdout.strip()
    child_env = {key: value for key, value in os.environ.items()
                 if key in {'WSL_INTEROP', 'WSL_DISTRO_NAME', 'PATH', 'SystemRoot', 'WINDIR', 'USBMUXD_WINDOWS_PORT'}}
    children = set()
    lock = threading.Lock()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(args.socket))
    os.chmod(args.socket, 0o600)
    server.listen(16)
    socket_inode = args.socket.stat().st_ino
    print(f'Relay ready: export USBMUXD_SOCKET_ADDRESS=UNIX:{args.socket}', flush=True)

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        while True:
            connection, _ = server.accept()
            threading.Thread(target=relay,
                             args=(connection, args.node, bridge, child_env, children, lock),
                             daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        try:
            if args.socket.stat().st_ino == socket_inode:
                args.socket.unlink()
        except FileNotFoundError:
            pass
        with lock:
            for child in children:
                if child.poll() is None:
                    child.terminate()
        print('Relay stopped', flush=True)


if __name__ == '__main__':
    main()

import importlib.util
from pathlib import Path
import os
import socket
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'windows/usbmuxd-relay.py'
SPEC = importlib.util.spec_from_file_location('usbmuxd_relay', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


@unittest.skipUnless(hasattr(os, 'getuid'), 'POSIX relay runs in WSL/Linux')
class RelayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_custom_shared_parent_is_never_chmodded(self):
        parent = self.root / 'shared'
        parent.mkdir(mode=0o755)
        with self.assertRaisesRegex(ValueError, 'private directory'):
            MODULE.prepare_socket_parent(parent / 'relay.sock')
        self.assertEqual(stat.S_IMODE(parent.stat().st_mode), 0o755)

    def test_new_parent_is_private_and_existing_files_preserved(self):
        endpoint = self.root / 'private/relay.sock'
        MODULE.prepare_socket_parent(endpoint)
        self.assertEqual(stat.S_IMODE(endpoint.parent.stat().st_mode), 0o700)
        endpoint.write_text('existing file')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            MODULE.prepare_socket_parent(endpoint)
        self.assertEqual(endpoint.read_text(), 'existing file')

    def test_failed_node_start_closes_the_client_connection(self):
        client, accepted = socket.socketpair()
        self.addCleanup(client.close)
        self.addCleanup(accepted.close)
        with patch.object(MODULE.subprocess, 'Popen', side_effect=OSError('synthetic interop failure')):
            MODULE.relay(accepted, '/fake/node', '/fake/bridge', {}, set(), threading.Lock())
        client.settimeout(1)
        self.assertEqual(client.recv(1), b'')


if __name__ == '__main__':
    unittest.main()

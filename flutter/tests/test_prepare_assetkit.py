"""Regression checks for safe, repeatable preparation of the patched package."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import stat
import subprocess
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare-assetkit.py'
SPEC = importlib.util.spec_from_file_location('prepare_assetkit', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.tools = Path(temporary.name)
        self.manifest = self.tools / 'Package.swift'
        self.manifest.write_text(MODULE.REMOTE)
        self.source = self.tools / '.build/checkouts/AssetKit'
        (self.source / MODULE.WRITER).parent.mkdir(parents=True)
        (self.source / MODULE.TEST).parent.mkdir(parents=True)
        (self.source / MODULE.WRITER).write_bytes(b'known original')
        (self.source / MODULE.WRITER).chmod(stat.S_IREAD)
        (self.source / 'LICENSE').write_text('MIT fixture')

    def test_prepare_is_repeatable_and_keeps_checkout_and_license(self):
        checksum = hashlib.sha256(b'known original').hexdigest()
        with patch.object(MODULE, 'UPSTREAM', checksum):
            MODULE.prepare(self.tools)
            MODULE.prepare(self.tools)
        self.assertEqual(self.manifest.read_text(), MODULE.LOCAL)
        self.assertEqual((self.source / MODULE.WRITER).read_bytes(), b'known original')
        self.assertEqual((self.tools / 'Patched/AssetKit/LICENSE').read_text(), 'MIT fixture')

    def test_unknown_upstream_is_rejected_without_manifest_changes(self):
        with self.assertRaisesRegex(ValueError, 'Unexpected upstream'):
            MODULE.prepare(self.tools)
        self.assertEqual(self.manifest.read_text(), MODULE.REMOTE)
        self.assertFalse((self.tools / 'Patched').exists())

    def test_unknown_dependency_is_rejected(self):
        self.manifest.write_text('a different dependency')
        with self.assertRaisesRegex(ValueError, 'Unexpected AssetKit dependency'):
            MODULE.prepare(self.tools)

    def test_modified_local_fix_is_preserved_and_rejected(self):
        checksum = hashlib.sha256(b'known original').hexdigest()
        with patch.object(MODULE, 'UPSTREAM', checksum):
            MODULE.prepare(self.tools)
        writer = self.tools / 'Patched/AssetKit' / MODULE.WRITER
        writer.write_bytes(b'user changes')
        with self.assertRaisesRegex(ValueError, 'Existing patched AssetKit differs'):
            MODULE.prepare(self.tools)
        self.assertEqual(writer.read_bytes(), b'user changes')

    def test_shipped_linker_patch_is_well_formed(self):
        native_patch = SCRIPT.parent / '../patches/omarchy-objc-linking-f6af7cf.patch'
        subprocess.run(['git', 'apply', '--numstat', str(native_patch)], check=True,
                       capture_output=True, text=True)

    def test_failed_copy_does_not_publish_a_partial_package_and_can_retry(self):
        checksum = hashlib.sha256(b'known original').hexdigest()

        def fail_copy(source, destination, **kwargs):
            destination.mkdir()
            (destination / 'partial').write_text('incomplete copy')
            raise OSError('synthetic interrupted copy')

        with patch.object(MODULE, 'UPSTREAM', checksum):
            with patch.object(MODULE.shutil, 'copytree', side_effect=fail_copy):
                with self.assertRaisesRegex(OSError, 'interrupted'):
                    MODULE.prepare(self.tools)
            self.assertFalse((self.tools / 'Patched/AssetKit').exists())
            self.assertEqual(self.manifest.read_text(), MODULE.REMOTE)
            MODULE.prepare(self.tools)
        self.assertEqual(self.manifest.read_text(), MODULE.LOCAL)


if __name__ == '__main__':
    unittest.main()

import importlib.util
import json
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify-ios-bundle.py'
SPEC = importlib.util.spec_from_file_location('verify_ios_bundle', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BundleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.bundle = root / 'Runner.app'
        self.source = root / 'app'
        self.bundle.mkdir()
        self.source.mkdir()
        (self.bundle / 'Runner').write_bytes(b'Mach-O fixture')
        (self.bundle / 'Info.plist').write_bytes(plistlib.dumps({
            'CFBundleExecutable': 'Runner', 'CFBundleIdentifier': 'test.app',
            'CFBundleShortVersionString': '1.0.0', 'CFBundleVersion': '7',
        }))
        (self.source / '.flutter-plugins-dependencies').write_text(json.dumps({
            'plugins': {'ios': [{'name': 'wakelock_plus'}]},
        }))
        self.catalog = self.source / 'ios/Runner/Assets.xcassets/AppIcon.appiconset'
        self.catalog.mkdir(parents=True)
        (self.catalog / 'Contents.json').write_text(json.dumps({'images': [
            {'filename': 'original.png', 'scale': '3x', 'size': '29x29'},
        ]}))
        (self.catalog / 'original.png').write_bytes(b'original icon')
        (self.bundle / 'AppIcon29x29@3x.png').write_bytes(b'original icon')

    def metadata(self, text):
        return patch.object(MODULE, 'linked_categories', return_value=text)

    def test_selector_reference_without_category_is_rejected(self):
        with self.metadata({'lock_idleTimerlockEnable:'}):
            with self.assertRaisesRegex(ValueError, 'Missing UIApplication'):
                MODULE.verify(self.bundle, self.source)

    def test_linked_category_and_original_icon_pass(self):
        with self.metadata({'idleTimerLock'}):
            result = MODULE.verify(self.bundle, self.source)
        self.assertTrue(result['wakelock_category'])
        self.assertEqual(result['original_icon_entries'], 1)

    def test_changed_icon_is_rejected(self):
        (self.bundle / 'AppIcon29x29@3x.png').write_bytes(b'wrong icon')
        with self.metadata({'idleTimerLock'}):
            with self.assertRaisesRegex(ValueError, 'differs from its source'):
                MODULE.verify(self.bundle, self.source)

    def test_universal_icon_and_no_wakelock_remain_supported(self):
        (self.source / '.flutter-plugins-dependencies').write_text(
            json.dumps({'plugins': {'ios': []}}))
        (self.catalog / 'Contents.json').write_text(json.dumps({'images': [
            {'filename': 'original.png', 'size': '1024x1024', 'idiom': 'universal'},
        ]}))
        with patch.object(MODULE, 'linked_categories') as command:
            result = MODULE.verify(self.bundle, self.source)
        command.assert_not_called()
        self.assertFalse(result['wakelock_category'])

    def test_reads_actual_macho_category_with_plain_and_chained_pointers(self):
        for chained in (0, 1 << 52):
            data = bytearray(512)
            base = 0x100000000
            struct.pack_into('<IIIIIIII', data, 0, 0xFEEDFACF, 0x100000C, 0, 2, 1, 152, 0, 0)
            struct.pack_into('<II16sQQQQiiII', data, 32,
                             0x19, 152, b'__DATA_CONST', base, 512, 0, 512, 7, 3, 1, 0)
            struct.pack_into('<16s16sQQIIIIIIII', data, 104,
                             b'__objc_catlist', b'__DATA_CONST', base + 256, 8,
                             256, 3, 0, 0, 0, 0, 0, 0)
            struct.pack_into('<Q', data, 256, (base + 264) | chained)
            struct.pack_into('<Q', data, 264, (base + 320) | chained)
            data[320:334] = b'idleTimerLock\0'
            (self.bundle / 'Runner').write_bytes(data)
            self.assertEqual(MODULE.linked_categories(self.bundle / 'Runner'), {'idleTimerLock'})


if __name__ == '__main__':
    unittest.main()

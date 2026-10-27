import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/swiftpm-objc-plugin-adapter.py'
SPEC = importlib.util.spec_from_file_location('objc_adapter', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.app = root / 'app'
        self.source = root / 'pub/demo_plugin'
        self.app.mkdir()
        self.classes = self.source / 'ios/Classes'
        self.classes.mkdir(parents=True)
        (self.classes / 'Demo.m').write_text('#import "Demo.h"\n')
        (self.classes / 'Demo.h').write_text('// synthetic public header\n')
        (self.app / '.flutter-plugins-dependencies').write_text(json.dumps({
            'plugins': {'ios': [{'name': 'demo_plugin', 'path': str(self.source)}]}}))
        self.overrides = self.app / 'pubspec_overrides.yaml'
        self.destination = self.app / 'build/plugin-adapters/demo_plugin'

    def test_override_is_inserted_inside_its_mapping(self):
        original = 'dependency_overrides:\n  other:\n    path: ../other\nresolution: workspace\n'
        self.overrides.write_text(original)
        MODULE.adapt(self.app, 'demo_plugin')
        updated = self.overrides.read_text()
        self.assertLess(updated.index('  demo_plugin:'), updated.index('resolution: workspace'))
        self.assertIn('  other:\n    path: ../other\n', updated)

    def test_decimal_ios_version_and_nested_sources(self):
        (self.classes / 'Nested').mkdir()
        (self.classes / 'Nested/Helper.m').write_text('#import "Helper.h"\n')
        (self.classes / 'Nested/Helper.h').write_text('// nested header\n')
        MODULE.adapt(self.app, 'demo_plugin', min_ios='15.0')
        package = self.destination / 'ios/demo_plugin'
        self.assertIn('.iOS("15.0")', (package / 'Package.swift').read_text())
        for relative in ['Nested/Helper.m', 'Nested/Helper.h', 'include/Nested/Helper.h']:
            self.assertTrue((package / 'Sources/demo_plugin' / relative).is_file())
        self.assertEqual((self.classes / 'Nested/Helper.m').read_text(), '#import "Helper.h"\n')

    def test_existing_override_fails_before_creating_adapter(self):
        original = 'dependency_overrides:\n  demo_plugin:\n    path: ../original\n'
        self.overrides.write_text(original)
        with self.assertRaisesRegex(ValueError, 'already overrides'):
            MODULE.adapt(self.app, 'demo_plugin')
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.overrides.read_text(), original)

    def test_inline_yaml_is_preserved_and_rejected(self):
        original = 'dependency_overrides: {other: any}\n'
        self.overrides.write_text(original)
        with self.assertRaisesRegex(ValueError, 'block mapping'):
            MODULE.adapt(self.app, 'demo_plugin')
        self.assertFalse(self.destination.exists())
        self.assertEqual(self.overrides.read_text(), original)

    def test_comment_substring_does_not_count_as_existing_override(self):
        self.overrides.write_text('# demo_plugin will be adapted\nother: value\n')
        MODULE.adapt(self.app, 'demo_plugin')
        self.assertIn('  demo_plugin:', self.overrides.read_text())

    def test_shared_darwin_swift_package_is_detected(self):
        package = self.source / 'darwin/demo_plugin'
        package.mkdir(parents=True)
        (package / 'Package.swift').write_text('// existing\n')
        with self.assertRaisesRegex(ValueError, 'already ships'):
            MODULE.adapt(self.app, 'demo_plugin')
        self.assertFalse(self.destination.exists())

    def test_nested_swift_sources_are_rejected(self):
        (self.classes / 'Nested').mkdir()
        (self.classes / 'Nested/Helper.swift').write_text('// requires a custom package\n')
        with self.assertRaisesRegex(ValueError, 'without Swift'):
            MODULE.adapt(self.app, 'demo_plugin')

    def test_invalid_input_cannot_create_an_adapter(self):
        for version in ['15.0); fatalError()', '-1', 'latest']:
            with self.assertRaisesRegex(ValueError, 'numeric'):
                MODULE.adapt(self.app, 'demo_plugin', min_ios=version)
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()

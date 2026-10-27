#!/usr/bin/env python3
"""Wrap a CocoaPods-only Objective-C Flutter plugin in a local Swift package.

Run flutter pub get first, then:
  swiftpm-objc-plugin-adapter.py <app> <plugin> [--frameworks UIKit,...]

Swift sources, resources and third-party pod dependencies require a custom
package. Existing overrides are preserved; unsupported YAML is rejected before
copying. Plugin sources are copied unchanged, including nested paths.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile


def render_overrides(text, plugin, destination):
    lines = text.splitlines(keepends=True)
    definition = re.compile(r"^(?:dependency_overrides|'dependency_overrides'|\"dependency_overrides\")\s*:")
    headers = [index for index, line in enumerate(lines) if definition.match(line)]
    if len(headers) > 1:
        raise ValueError('Duplicate dependency_overrides mappings; review the YAML first.')
    path = json.dumps(str(destination), ensure_ascii=False)
    if not headers:
        return text.rstrip('\n') + f'\ndependency_overrides:\n  {plugin}:\n    path: {path}\n'
    start = headers[0]
    tail = lines[start].split(':', 1)[1].strip()
    if tail and not tail.startswith('#'):
        raise ValueError('dependency_overrides must use a block mapping, not an inline value.')
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and not line.startswith((' ', '#', '\n', '\r')):
            break
        if '\t' in line[:len(line) - len(line.lstrip())]:
            raise ValueError('Tabs in YAML indentation are unsupported.')
        end += 1
    content = [line for line in lines[start + 1:end] if line.strip() and not line.lstrip().startswith('#')]
    indent = min((len(line) - len(line.lstrip()) for line in content), default=2)
    if indent < 1:
        raise ValueError('Invalid dependency_overrides mapping.')
    key = re.compile(rf"^ {{{indent}}}(?:{re.escape(plugin)}|'{re.escape(plugin)}'|\"{re.escape(plugin)}\")\s*:")
    if any(key.match(line) for line in content):
        raise ValueError(f'dependency_overrides already overrides {plugin}; preserve and review it.')
    entry = f"{' ' * indent}{plugin}:\n{' ' * (indent + 2)}path: {path}\n"
    prefix = ''.join(lines[:end]).rstrip('\n') + '\n'
    return prefix + entry + ''.join(lines[end:])


def adapt(app, plugin, destination=None, frameworks='UIKit', min_ios='13'):
    if not re.fullmatch(r'[a-z][a-z0-9_]*', plugin):
        raise ValueError('Plugin name must be a Dart package identifier.')
    if not re.fullmatch(r'[1-9][0-9]*(?:\.[0-9]+){0,2}', min_ios):
        raise ValueError('Minimum iOS version must be numeric, for example 13 or 15.0.')
    version = min_ios if '.' in min_ios else min_ios + '.0'
    linked = [name.strip() for name in frameworks.split(',') if name.strip()]
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) for name in linked):
        raise ValueError('Invalid framework name.')
    app = app.resolve()
    plugins = json.loads((app / '.flutter-plugins-dependencies').read_text())
    entry = next((item for item in plugins['plugins']['ios'] if item['name'] == plugin), None)
    if entry is None:
        raise ValueError(f'{plugin} is not an iOS plugin of {app}')
    source = Path(entry['path']).resolve()
    if any((source / platform / plugin / 'Package.swift').exists() for platform in ('ios', 'darwin')):
        raise ValueError(f'{plugin} already ships a Swift package; no adapter needed')
    classes = source / 'ios/Classes'
    sources = sorted(path for path in classes.rglob('*') if path.suffix in {'.m', '.mm', '.c', '.cpp', '.h', '.hpp'})
    if not any(path.suffix in {'.m', '.mm'} for path in sources) or any(classes.rglob('*.swift')):
        raise ValueError('Only Objective-C plugins without Swift sources in ios/Classes are supported.')
    destination = (destination or app / 'build/plugin-adapters' / plugin).resolve()
    if destination.exists() or destination.is_relative_to(source):
        raise ValueError('Adapter destination exists or is inside the source; choose a fresh path.')
    overrides = app / 'pubspec_overrides.yaml'
    if overrides.is_symlink():
        raise ValueError('pubspec_overrides.yaml is a symlink; preserve and review it.')
    text = overrides.read_text() if overrides.exists() else ''
    updated = render_overrides(text, plugin, destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f'.{plugin}-', dir=destination.parent) as temporary:
        staged = Path(temporary) / plugin
        shutil.copytree(source, staged, ignore=shutil.ignore_patterns('.git', '.build', '.dart_tool', 'build'))
        package = staged / 'ios' / plugin
        target = package / 'Sources' / plugin
        (target / 'include').mkdir(parents=True)
        for path in sources:
            relative = path.relative_to(classes)
            copied = target / relative
            copied.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, copied)
            if path.suffix in {'.h', '.hpp'}:
                header = target / 'include' / relative
                header.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, header)
        settings = ', '.join(f'.linkedFramework("{name}")' for name in linked)
        (package / 'Package.swift').write_text(f'''// swift-tools-version: 5.9
// Generated by xtool-flutter; original plugin sources are unchanged.
import PackageDescription
let package = Package(
    name: "{plugin}",
    platforms: [.iOS("{version}")],
    products: [.library(name: "{plugin}", targets: ["{plugin}"])],
    targets: [.target(
        name: "{plugin}",
        publicHeadersPath: "include",
        cSettings: [.unsafeFlags(["-fobjc-arc"])],
        linkerSettings: [{settings}]
    )]
)
''')
        # Prepare the new YAML on the app's filesystem before publishing the
        # adapter. A failed write must not truncate existing overrides.
        with tempfile.TemporaryDirectory(prefix='.pubspec-overrides-', dir=app) as yaml_directory:
            yaml_file = Path(yaml_directory) / 'pubspec_overrides.yaml'
            yaml_file.write_text(updated)
            staged.rename(destination)
            yaml_file.replace(overrides)
    print(f'Adapter: {destination / "ios" / plugin}\nRun flutter pub get again.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('plugin')
    parser.add_argument('--frameworks', default='UIKit')
    parser.add_argument('--min-ios', default='13')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    try:
        adapt(args.app, args.plugin, args.out, args.frameworks, args.min_ios)
    except (ValueError, OSError) as error:
        parser.exit(1, f'{error}\n')

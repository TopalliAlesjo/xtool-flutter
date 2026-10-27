#!/usr/bin/env python3
"""Prepare a pinned, local AssetKit copy with the CoreUI bitmap stride fix.

Run after `swift package resolve` in darwin-tools. Never edits .build/checkouts.
Unknown upstream files or changes to an existing patched copy fail closed.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import stat
import tempfile

UPSTREAM = 'f92aacb3bed2b0f3df6a5ce2d114363e3113c29539eee37a18e283be78d0b2f1'
REMOTE = '.package(url: "https://github.com/joshuaswarren/AssetKit", revision: "705ce2f2b797835cf4bac65e0dff1e9ca37ba0bf"),'
LOCAL = '.package(path: "Patched/AssetKit"),'
WRITER = Path('Sources/AssetKit/CAR/MLECBody.swift')
TEST = Path('Tests/AssetKitTests/AssetKitRowStrideTests.swift')
COMPILED_TEST = Path('Tests/AssetKitTests/CompiledIconTests.swift')
HERE = Path(__file__).resolve().parent


def prepare(tools):
    tools = tools.resolve()
    manifest = tools / 'Package.swift'
    text = manifest.read_text()
    if text.count(REMOTE) != 1 and text.count(LOCAL) != 1:
        raise ValueError('Unexpected AssetKit dependency; review the pinned version.')
    source = tools / '.build/checkouts/AssetKit'
    destination = tools / 'Patched/AssetKit'
    replacements = {
        WRITER: (HERE / '../patches/MLECBody.swift').read_bytes(),
        TEST: (HERE / '../tests/AssetKitRowStrideTests.swift').read_bytes(),
        COMPILED_TEST: (HERE / '../tests/CompiledIconTests.swift').read_bytes(),
    }
    if destination.exists():
        for relative, data in replacements.items():
            if not (destination / relative).is_file() or (destination / relative).read_bytes() != data:
                raise ValueError(f'Existing patched AssetKit differs: {relative}; preserve and review it.')
    else:
        if hashlib.sha256((source / WRITER).read_bytes()).hexdigest() != UPSTREAM:
            raise ValueError('Unexpected upstream MLECBody.swift; refusing to patch.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.AssetKit-', dir=destination.parent) as temporary:
            staged = Path(temporary) / 'AssetKit'
            shutil.copytree(source, staged,
                            ignore=shutil.ignore_patterns('.git', '.build', '.swiftpm'))
            for relative, data in replacements.items():
                target = staged / relative
                # SwiftPM makes checkout files read-only; only the local copy changes.
                if target.exists():
                    target.chmod(target.stat().st_mode | stat.S_IWUSR)
                target.write_bytes(data)
            staged.rename(destination)
    if REMOTE in text:
        with tempfile.TemporaryDirectory(prefix='.assetkit-manifest-', dir=tools) as temporary:
            staged_manifest = Path(temporary) / 'Package.swift'
            staged_manifest.write_text(text.replace(REMOTE, LOCAL))
            staged_manifest.replace(manifest)
    print(f'AssetKit bitmap stride fix ready: {destination}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('darwin_tools', type=Path)
    prepare(parser.parse_args().darwin_tools)

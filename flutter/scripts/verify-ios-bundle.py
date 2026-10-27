#!/usr/bin/env python3
"""Check the final Runner's native wake-lock category and original app icons.

The Objective-C exception cannot be caught by Dart. Inspect the linked metadata,
not just selector strings: the old binary contains the call but lacks its method.
"""
import argparse
import json
from pathlib import Path
import plistlib
import struct


def linked_categories(executable):
    """Read category names from arm64 Mach-O metadata, including chained rebases.

    LLVM 18's objc dump does not decode the chained pointers written by lld;
    its output omits even categories present in the executable.
    """
    data = executable.read_bytes()
    if data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('Expected a thin 64-bit Mach-O Runner.')
    segments = []
    categories = None
    position = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        command, size = struct.unpack_from('<II', data, position)
        if command == 0x19:  # LC_SEGMENT_64
            vmaddr, _, fileoff, filesize = struct.unpack_from('<QQQQ', data, position + 24)
            segments.append((vmaddr, fileoff, filesize))
            count = struct.unpack_from('<I', data, position + 64)[0]
            for index in range(count):
                section = position + 72 + index * 80
                name = data[section:section + 16].split(b'\0')[0]
                if name == b'__objc_catlist':
                    length, offset = struct.unpack_from('<QI', data, section + 40)
                    categories = (offset, length)
        position += size
    if categories is None:
        return set()
    imagebase = next(address for address, offset, length in segments if offset == 0 and length)

    def pointer_offset(pointer):
        target = pointer & ((1 << 36) - 1)  # DYLD_CHAINED_PTR_64 rebase target
        for candidate in (pointer, target, imagebase + target):
            for address, offset, length in segments:
                if address <= candidate < address + length:
                    return offset + candidate - address
        raise ValueError('Invalid Objective-C metadata pointer.')

    result = set()
    offset, length = categories
    for entry in range(offset, offset + length, 8):
        category = pointer_offset(struct.unpack_from('<Q', data, entry)[0])
        name = pointer_offset(struct.unpack_from('<Q', data, category)[0])
        end = data.index(b'\0', name)
        result.add(data[name:end].decode('utf-8'))
    return result


def verify(bundle, source):
    info = plistlib.loads((bundle / 'Info.plist').read_bytes())
    executable = bundle / info['CFBundleExecutable']
    if not executable.is_file():
        raise ValueError('Missing Runner executable.')
    plugins = json.loads((source / '.flutter-plugins-dependencies').read_text())
    wakelock = any(plugin['name'] == 'wakelock_plus'
                   for plugin in plugins['plugins']['ios'])
    if wakelock:
        if 'idleTimerLock' not in linked_categories(executable):
            raise ValueError('Missing UIApplication idleTimerLock category: link Runner with -ObjC.')
    catalog = source / 'ios/Runner/Assets.xcassets/AppIcon.appiconset'
    icons = json.loads((catalog / 'Contents.json').read_text())['images']
    checked = 0
    for icon in icons:
        if not icon.get('filename'):
            continue
        if 'scale' not in icon:
            # Single-size universal icons are resized by actool; their loose
            # renditions cannot be compared byte-for-byte to the 1024px source.
            continue
        # Multi-size AppIcon output emitted by the pinned Linux actool.
        scale = icon['scale']
        suffix = '' if scale == '1x' else f'@{scale}'
        name = f"AppIcon{icon['size']}{suffix}.png"
        if (bundle / name).read_bytes() != (catalog / icon['filename']).read_bytes():
            raise ValueError(f'Compiled loose icon differs from its source: {name}')
        checked += 1
    return {'bundle_id': info['CFBundleIdentifier'],
            'version': info['CFBundleShortVersionString'], 'build': info['CFBundleVersion'],
            'original_icon_entries': checked, 'wakelock_category': wakelock}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.bundle, args.source), indent=2))

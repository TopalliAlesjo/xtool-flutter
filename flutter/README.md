# flutter/

Helpers for building Flutter iOS apps on Linux/WSL2 and installing them with xtool.
How to use them, in order: [Documentation/Flutter/GUIDE.md](../Documentation/Flutter/GUIDE.md).

| File | Runs on | Purpose |
| --- | --- | --- |
| `scripts/env.sh.example` | WSL | Copy to `~/xtool-flutter-lab/env.sh`; puts Swift, LLVM, xtool, Flutter and native libs on `PATH` |
| `scripts/build-native-deps.sh` | WSL | Builds the pinned libimobiledevice stack into the lab, no sudo |
| `scripts/prepare-flutter-ios.sh` | WSL | Pinned omarchy-apple-dev + patch, Linux `actool`, Linux-hosted iOS `gen_snapshot` |
| `scripts/prepare-assetkit.py` | WSL | Pinned local AssetKit with corrected bitmap row padding |
| `scripts/verify-ios-bundle.py` | WSL | Final Mach-O wake-lock category and original loose icons gate |
| `scripts/build-ipa.sh` | WSL | Release arm64 IPA of a Flutter app |
| `scripts/swiftpm-objc-plugin-adapter.py` | WSL | Swift package wrapper for an Objective-C-only plugin |
| `patches/omarchy-apple-dev-f6af7cf.patch` | — | Explicit `ACTOOL`, `APP_DISPLAY_NAME`, privacy manifest copy |
| `windows/install-apple-mobile-device-support.ps1` | Windows | Installs Apple's iPhone USB service only, after checking Apple's signature |
| `windows/usbmuxd-relay.py` + `usbmuxd-bridge.cjs` | WSL + Windows | Private UNIX socket in WSL → Apple service on `127.0.0.1:27015` |

Shell and Python files must keep LF line endings (see `.gitattributes`).

The [27 October native runner and icon fixes](../Documentation/Flutter/IOS-FIXES.md)
explain the `-ObjC` linker flag, bitmap stride correction and regression commands.

[Maintenance and portable checks](../Documentation/Flutter/TOOLING-TESTS.md) cover
the adapter, interrupted preparation, USB relay and CLI storage/upload fixes.
Custom socket parents must be private (`0700`) and owned by the current Linux
user; shared directories are refused without changing their permissions.

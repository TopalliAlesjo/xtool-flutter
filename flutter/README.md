# flutter/

Helpers for building Flutter iOS apps on Linux/WSL2 and installing them with xtool.
How to use them, in order: [Documentation/Flutter/GUIDE.md](../Documentation/Flutter/GUIDE.md).

| File | Runs on | Purpose |
| --- | --- | --- |
| `scripts/env.sh.example` | WSL | Copy to `~/xtool-flutter-lab/env.sh`; puts Swift, LLVM, xtool, Flutter and native libs on `PATH` |
| `scripts/build-native-deps.sh` | WSL | Builds the pinned libimobiledevice stack into the lab, no sudo |
| `scripts/prepare-flutter-ios.sh` | WSL | Pinned omarchy-apple-dev + patch, Linux `actool`, Linux-hosted iOS `gen_snapshot` |
| `scripts/build-ipa.sh` | WSL | Release arm64 IPA of a Flutter app |
| `scripts/swiftpm-objc-plugin-adapter.py` | WSL | Swift package wrapper for an Objective-C-only plugin |
| `patches/omarchy-apple-dev-f6af7cf.patch` | — | Explicit `ACTOOL`, `APP_DISPLAY_NAME`, privacy manifest copy |
| `windows/install-apple-mobile-device-support.ps1` | Windows | Installs Apple's iPhone USB service only, after checking Apple's signature |
| `windows/usbmuxd-relay.py` + `usbmuxd-bridge.cjs` | WSL + Windows | Private UNIX socket in WSL → Apple service on `127.0.0.1:27015` |

Shell and Python files must keep LF line endings (see `.gitattributes`).

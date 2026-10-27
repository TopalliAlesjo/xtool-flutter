# xtool-flutter

**Build a Flutter app for iOS on Windows and install it on your own iPhone — no Mac, no macOS VM.**

xtool-flutter is a fork of [xtool](https://github.com/xtool-org/xtool) plus a
documented pipeline that compiles a Flutter app to a release arm64 IPA inside WSL2,
signs it with a free Apple ID and installs it over USB.

> **Status: experimental.** Proven end to end once: a real Flutter app with eight
> native plugins was built on Windows 11 + WSL2, installed on an iPhone running
> iOS 27, opened, logged in and showed live data. Release builds only, no hot
> reload, no App Store upload. Read [Limits](Documentation/Flutter/GUIDE.md#limits)
> before you start.

## What you get

- Flutter **release** IPA for physical iPhones/iPads (arm64), built on Linux/WSL2.
- Signing and install with a **free Apple ID** via `xtool install`.
- Native plugins compiled as Swift packages; a helper wraps Objective-C-only plugins.
- A USB path that works from WSL: Apple's own Windows driver, bridged into WSL by a
  small local relay (USB/IP stalls during uploads).

## Quick start

The full walkthrough with every command is in
**[Documentation/Flutter/GUIDE.md](Documentation/Flutter/GUIDE.md)**. In short:

```bash
# Windows: wsl --install -d Ubuntu-24.04, then inside Ubuntu:
git clone https://github.com/TopalliAlesjo/xtool-flutter.git ~/xtool-flutter-lab/xtool
cp ~/xtool-flutter-lab/xtool/flutter/scripts/env.sh.example ~/xtool-flutter-lab/env.sh
source ~/xtool-flutter-lab/env.sh            # after installing Swift (guide step 2)

cd ~/xtool-flutter-lab/xtool
bash flutter/scripts/build-native-deps.sh    # pinned libimobiledevice stack
swift build --configuration release --product xtool
xtool sdk install /mnt/c/Users/<you>/Downloads/Xcode_27.xip   # iOS SDK from Apple's Xcode.xip

# Flutter for Linux, same version as your app, then the iOS AOT compiler (once):
git clone --branch 3.47.5 --depth 1 https://github.com/flutter/flutter.git ~/xtool-flutter-lab/toolchains/flutter
bash flutter/scripts/prepare-flutter-ios.sh

# Build:
cd ~/xtool-flutter-lab/apps/my_app && flutter pub get
APP_DISPLAY_NAME="My App" bash ~/xtool-flutter-lab/xtool/flutter/scripts/build-ipa.sh .

# Install (Apple Mobile Device Support on Windows + relay running, see guide step 8):
export USBMUXD_SOCKET_ADDRESS="UNIX:$HOME/xtool-flutter-lab/runtime/windows-usbmuxd.sock"
xtool auth login --mode password
xtool install --usb build/ios-linux/Runner.ipa
```

Then on the phone: enable **Developer Mode**, trust your own **Apple Development**
certificate in *Settings → General → VPN & Device Management*, and open the app.

## Requirements

Windows 10/11 x64 with WSL2 · ~60 GB free disk · free Apple ID (a secondary one is
recommended) · iPhone/iPad + USB cable · Node.js and 7-Zip on Windows · Xcode `.xip`
downloaded from Apple (used only as the iOS SDK source).

## Documentation

| Document | Contents |
| --- | --- |
| [GUIDE.md](Documentation/Flutter/GUIDE.md) | Setup from zero, build, install, daily loop, limits, security, tested versions |
| [TROUBLESHOOTING.md](Documentation/Flutter/TROUBLESHOOTING.md) | Every error met so far and its fix |
| [TOOLING-TESTS.md](Documentation/Flutter/TOOLING-TESTS.md) | Regression checks, CLI robustness fixes, private USB relay and maintenance |
| [flutter/](flutter) | Scripts: native deps, iOS toolchain prep, IPA build, plugin adapter, Windows USB relay |

## How it works

Flutter's iOS AOT compiler (`gen_snapshot`) is rebuilt for Linux from the Dart
revision your Flutter pins; Runner and the plugins are compiled with SwiftPM against
the iOS SDK that `xtool sdk` extracts from Xcode.xip; icons and storyboards go
through Linux re-implementations of `actool`/`ibtool`; `xtool` provisions, signs and
installs. Details in the [guide](Documentation/Flutter/GUIDE.md#how-it-works).

## Credits and license

- [xtool](https://github.com/xtool-org/xtool) by Kabir Oberai — MIT. This fork tracks
  upstream releases and includes [targeted CLI robustness fixes](Documentation/Flutter/TOOLING-TESTS.md).
- [omarchy-apple-dev](https://github.com/joshuaswarren/omarchy-apple-dev) by Joshua
  Warren — MIT. Its Flutter-on-Linux build (Linux `gen_snapshot`, SwiftPM shell
  package, `actool`/`ibtool`) is the core of the IPA build; it is fetched at a pinned
  commit and patched, not vendored.
- [libimobiledevice](https://libimobiledevice.org) — LGPL-2.1, built from source, not redistributed.

This repository is MIT-licensed ([LICENSE.md](LICENSE.md)). It is not affiliated with
Apple, Google or the Flutter team. It relies on Apple's private developer-service
APIs; use it with your own devices and accounts, under Apple's terms.

---

# xtool (upstream)

Cross-platform Xcode replacement. Build and deploy iOS apps with SwiftPM on Linux, Windows, and macOS.

## Overview

xtool is a cross-platform (Linux/WSL/macOS) tool that replicates Xcode functionality with open standards.

✅ Build a SwiftPM package into an iOS app

✅ Sign and install iOS apps

✅ Interact with Apple Developer Services programmatically

## Getting Started

1. Follow the guide to install `xtool`
    - [Installation (Linux/Windows)](https://xtool.sh/documentation/xtooldocs/installation-linux)
    - [Installation (macOS)](https://xtool.sh/documentation/xtooldocs/installation-macos)
2. Create and run your first xtool-powered app by following the [tutorial](https://xtool.sh/tutorials/xtooldocs/first-app)!

## Examples

### Screenshot

![A screenshot of xtool being invoked from VSCode](Documentation/xtool.docc/Resources/Cover.png)

### Command line interface

```bash
$ xtool --help
OVERVIEW: Cross-platform Xcode replacement

USAGE: xtool <subcommand>

OPTIONS:
  -h, --help              Show help information.

CONFIGURATION SUBCOMMANDS:
  setup                   Set up xtool for iOS development
  auth                    Manage Apple Developer Services authentication
  sdk                     Manage the Darwin Swift SDK

DEVELOPMENT SUBCOMMANDS:
  new                     Create a new xtool SwiftPM project
  dev                     Build and run an xtool SwiftPM project
  ds                      Interact with Apple Developer Services

DEVICE SUBCOMMANDS:
  devices                 List devices
  install                 Install an ipa file to your device
  uninstall               Uninstall an installed app
  launch                  Launch an installed app

  See 'xtool help <subcommand>' for detailed help.
```

### Library

xtool includes a library that you can use to interact with Apple Developer Services, iOS devices, and more from your own app. You can use this by adding `XKit` as a SwiftPM dependency.

```swift
// package dependency:
.package(url: "https://github.com/xtool-org/xtool", .upToNextMinor(from: "1.2.0"))
// target dependency:
.product(name: "XKit", package: "xtool")
```

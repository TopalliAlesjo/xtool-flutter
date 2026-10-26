# Flutter iOS apps from Windows (WSL2), step by step

This guide takes you from a clean Windows PC to a Flutter app running on your own
iPhone, signed with a free Apple ID, without a Mac or a macOS VM.

It is **experimental**. It was done end to end once (see
[Tested configuration](#tested-configuration)); every step below is one that was
actually run, but the helper scripts in [`flutter/`](../../flutter) package those
steps and have not yet been re-run as a whole on a second machine. Expect to
debug. [Troubleshooting](TROUBLESHOOTING.md) lists every failure hit so far.

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [1. Ubuntu in WSL2](#1-ubuntu-in-wsl2)
- [2. Swift toolchain](#2-swift-toolchain)
- [3. xtool and its native libraries](#3-xtool-and-its-native-libraries)
- [4. iOS SDK from Xcode.xip](#4-ios-sdk-from-xcodexip)
- [5. Flutter for Linux](#5-flutter-for-linux)
- [6. iOS compiler and asset tools](#6-ios-compiler-and-asset-tools)
- [7. Build your app's IPA](#7-build-your-apps-ipa)
- [8. Connect the iPhone](#8-connect-the-iphone)
- [9. Sign in, install, trust](#9-sign-in-install-trust)
- [Day-to-day loop](#day-to-day-loop)
- [Limits](#limits)
- [Security and privacy](#security-and-privacy)
- [Tested configuration](#tested-configuration)

## How it works

| Stage | What Xcode normally does | What does it here |
| --- | --- | --- |
| Dart → iOS machine code | `gen_snapshot` (macOS binary) | `gen_snapshot` built for Linux from the Dart revision your Flutter pins ([omarchy-apple-dev](https://github.com/joshuaswarren/omarchy-apple-dev) `flutter/setup.sh`) |
| Runner + native plugins | Xcode build + CocoaPods | One Swift package compiled with SwiftPM/SwiftBuild against the iOS SDK (`xtool sdk`) |
| Icons, launch screen, Info.plist | `actool`, `ibtool` | Linux re-implementations from omarchy-apple-dev |
| Signing + provisioning | Xcode + your Apple ID | `xtool install` (free Apple ID, development certificate) |
| USB to the iPhone | Apple's driver on macOS | Apple Mobile Device Support on **Windows**, bridged into WSL by [`usbmuxd-relay.py`](../../flutter/windows/usbmuxd-relay.py) |

You need an `.xip` of Xcode only as a source of the iOS SDK headers and libraries;
nothing from it runs.

## Requirements

- Windows 10/11 x64 with WSL2 and admin rights (driver install, WSL install).
- About **60 GB free** on the system drive: Dart SDK sources and build (~10 GB),
  Xcode.xip + extracted SDK (~15 GB), Flutter and caches, your app's build.
- A free [Apple ID](https://appleid.apple.com). A **secondary** Apple ID is
  recommended: login goes through Apple's private authentication APIs.
- An iPhone or iPad with a USB data cable.
- On Windows: [Node.js](https://nodejs.org) (for the USB bridge) and [7-Zip](https://www.7-zip.org).
- Your Flutter app's source. Pin the Flutter version it was written for.

All Linux commands below run inside Ubuntu as your normal user. Everything lives
under one folder, `~/xtool-flutter-lab` (override with `XTOOL_FLUTTER_LAB`).

## 1. Ubuntu in WSL2

PowerShell:

```powershell
wsl --install -d Ubuntu-24.04
```

Open Ubuntu, create your user, then:

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  build-essential git curl ca-certificates gnupg pkg-config python3 python3-venv \
  zip unzip file rsync llvm-18 libssl-dev libcurl4-openssl-dev libxml2-dev \
  libz3-dev zlib1g-dev liblzma-dev libncurses-dev libedit2 libsqlite3-0 \
  libpython3-dev libatomic1 autoconf automake libtool-bin libusb-1.0-0-dev usbutils
```

`liblzma-dev` is easy to miss: without it the xtool build fails at link time.

## 2. Swift toolchain

Use an official [swift.org](https://www.swift.org/install/linux/) release for
Ubuntu 24.04 (tested: 6.4.0; current xtool targets 6.4.1). Verify its signature:

```bash
mkdir -p ~/xtool-flutter-lab/{artifacts,toolchains}
cd ~/xtool-flutter-lab/artifacts
v=6.4.1   # pick the release you want
f=swift-$v-RELEASE-ubuntu24.04.tar.gz
curl -fLO https://download.swift.org/swift-$v-release/ubuntu2404/swift-$v-RELEASE/$f
curl -fLO https://download.swift.org/swift-$v-release/ubuntu2404/swift-$v-RELEASE/$f.sig
curl -fL --compressed https://www.swift.org/keys/release-key-swift-6.x.asc | gpg --import
gpg --verify $f.sig $f        # must say "Good signature" from swift.org
mkdir -p ../toolchains/swift
tar -xzf $f -C ../toolchains/swift --strip-components=1
```

Note `--compressed`: the key file is served gzip-encoded and `gpg` rejects it otherwise.

Install the environment file and load it:

```bash
git clone https://github.com/TopalliAlesjo/xtool-flutter.git ~/xtool-flutter-lab/xtool
cp ~/xtool-flutter-lab/xtool/flutter/scripts/env.sh.example ~/xtool-flutter-lab/env.sh
source ~/xtool-flutter-lab/env.sh
swift --version
```

Run `source ~/xtool-flutter-lab/env.sh` in **every** new shell from now on.

## 3. xtool and its native libraries

Ubuntu's libimobiledevice is too old for xtool, so build the pinned stack into the
lab (no sudo), then xtool itself:

```bash
cd ~/xtool-flutter-lab/xtool
bash flutter/scripts/build-native-deps.sh
swift build --configuration release --product xtool
xtool --help
```

## 4. iOS SDK from Xcode.xip

1. Sign in at <https://developer.apple.com/download/all/?q=Xcode> with your Apple ID
   and download a stable **Xcode .xip** (tested: Xcode 27.0, ~2 GB). Downloading it
   means accepting Apple's Xcode license; it stays on your machine.
2. Install the SDK from it (adjust the Windows path):

```bash
xtool sdk install /mnt/c/Users/<you>/Downloads/Xcode_27.xip
xtool sdk status
```

## 5. Flutter for Linux

Use the **same Flutter version** your app uses (`flutter --version` on your usual
machine, or the `.metadata`/CI config of the project):

```bash
cd ~/xtool-flutter-lab/toolchains
git clone --branch 3.47.5 --single-branch --depth 1 https://github.com/flutter/flutter.git flutter
flutter --version
flutter precache --ios --no-android --no-web --no-linux --no-windows --no-macos --no-fuchsia --no-universal
```

(`flutter` is already on `PATH` through `env.sh`.) If `flutter --version` cannot
determine the engine version from a shallow clone, see
[Troubleshooting](TROUBLESHOOTING.md#flutter-cannot-determine-the-engine-version).

## 6. iOS compiler and asset tools

```bash
bash ~/xtool-flutter-lab/xtool/flutter/scripts/prepare-flutter-ios.sh
```

This clones omarchy-apple-dev at a pinned commit, applies
[our small patch](../../flutter/patches/omarchy-apple-dev-f6af7cf.patch), builds the
Linux `actool`, and builds Dart's `gen_snapshot` for iOS. The last step downloads
~7 GB of Dart sources and Google-hosted build tools and runs for a long time. It is
done once per Flutter version; the original macOS `gen_snapshot` is kept as
`gen_snapshot_arm64.macos` in the Flutter cache.

## 7. Build your app's IPA

Work on a copy of your app inside WSL (building on `/mnt/c` is much slower):

```bash
rsync -a --exclude build --exclude .dart_tool /mnt/c/path/to/my_app/ ~/xtool-flutter-lab/apps/my_app/
cd ~/xtool-flutter-lab/apps/my_app
flutter pub get
```

**Check plugins.** Every iOS plugin must ship a Swift package
(`ios/<plugin>/Package.swift` or `darwin/<plugin>/Package.swift`); CocoaPods is not
available. List the ones that do not:

```bash
python3 - <<'PY'
import json, pathlib
d = json.loads(pathlib.Path('.flutter-plugins-dependencies').read_text())
for p in d['plugins']['ios']:
    root = pathlib.Path(p['path'])
    ok = any((root / s / p['name'] / 'Package.swift').exists() for s in ('ios', 'darwin'))
    print(('ok      ' if ok else 'MISSING ') + p['name'])
PY
```

For a pure Objective-C plugin, generate a local wrapper (sources untouched):

```bash
python3 ~/xtool-flutter-lab/xtool/flutter/scripts/swiftpm-objc-plugin-adapter.py . open_filex
flutter pub get
```

Plugins with Swift sources but no `Package.swift`, resources, or pod dependencies
need a hand-written `Package.swift`, or a newer plugin version that has one.

**Build:**

```bash
APP_DISPLAY_NAME="My App" \
bash ~/xtool-flutter-lab/xtool/flutter/scripts/build-ipa.sh . \
  API_BASE_URL=https://example.com/api   # optional --dart-define values
```

The result is `build/ios-linux/Runner.ipa`: release mode, arm64, not yet signed.
Optional overrides: `BUNDLE_ID`, `BUILD_NAME`, `BUILD_NUMBER`, `MIN_IOS`.

## 8. Connect the iPhone

USB/IP (`usbipd-win`) can attach the iPhone to WSL and pair it, but in testing the
app upload stalled every time. The reliable path is Apple's own Windows driver,
bridged into WSL.

**On Windows, once:**

1. Download `iTunes64Setup.exe` from <https://www.apple.com/itunes/download/win64>.
2. Extract only the driver package (iTunes itself is not installed):
   ```powershell
   & "C:\Program Files\7-Zip\7z.exe" e .\iTunes64Setup.exe AppleMobileDeviceSupport64.msi -o.\amds
   ```
3. Install it (checks Apple's signature, asks for admin consent):
   ```powershell
   powershell -ExecutionPolicy Bypass -File flutter\windows\install-apple-mobile-device-support.ps1 -Msi .\amds\AppleMobileDeviceSupport64.msi
   ```
   (run from a Windows checkout of this repository, or give the full path to the script).
4. Plug in the iPhone, unlock it, tap **Trust** and enter the passcode.

If you previously attached the phone to WSL with `usbipd`, give it back to Windows
first: `usbipd detach --busid <id>` and `usbipd unbind --busid <id>`.

**In WSL, each session** — terminal 1:

```bash
source ~/xtool-flutter-lab/env.sh
python3 ~/xtool-flutter-lab/xtool/flutter/windows/usbmuxd-relay.py
```

Terminal 2:

```bash
source ~/xtool-flutter-lab/env.sh
export USBMUXD_SOCKET_ADDRESS="UNIX:$HOME/xtool-flutter-lab/runtime/windows-usbmuxd.sock"
xtool devices
```

## 9. Sign in, install, trust

Still in terminal 2:

```bash
xtool auth login --mode password
```

Type your Apple ID, password and 2FA code **only into this terminal**. xtool asks a
third-party service for anonymous device-identification ("anisette") data; the
credentials themselves go to Apple. The session is stored for later runs.

```bash
xtool install --usb build/ios-linux/Runner.ipa
```

First time on a phone:

1. **Developer Mode.** The first install of a development-signed app makes
   *Settings → Privacy & Security → Developer Mode* appear. Turn it on, restart,
   confirm **Turn On** after unlocking, then run `xtool install` again.
2. **Trust your certificate.** Opening the app shows *Untrusted Developer*. Go to
   *Settings → General → VPN & Device Management*, open the **Apple Development**
   entry with **your own Apple ID**, check your app is listed, tap **Trust**. This
   is not a management profile; never install a profile you didn't expect.
3. Open the app from the Home Screen.

xtool adds a team-specific prefix to the bundle ID (free accounts cannot use an
arbitrary one), so the installed app does not replace an App Store copy.

## Day-to-day loop

```bash
source ~/xtool-flutter-lab/env.sh
# terminal 1: python3 ~/xtool-flutter-lab/xtool/flutter/windows/usbmuxd-relay.py
export USBMUXD_SOCKET_ADDRESS="UNIX:$HOME/xtool-flutter-lab/runtime/windows-usbmuxd.sock"
rsync -a --exclude build --exclude .dart_tool /mnt/c/path/to/my_app/ ~/xtool-flutter-lab/apps/my_app/
cd ~/xtool-flutter-lab/apps/my_app
bash ~/xtool-flutter-lab/xtool/flutter/scripts/build-ipa.sh .
xtool install --usb build/ios-linux/Runner.ipa
```

With a free Apple ID the provisioning profile expires after **7 days**: reinstall to
renew it. The app's data is kept on reinstall.

## Limits

- **Release builds only.** No debug mode, hot reload, `flutter run` or attached
  debugger. `xtool launch` failed in testing; open the app by tapping its icon.
- **No CocoaPods.** Plugins need a Swift package (see step 7). Flavors/schemes are
  not handled.
- **Free Apple ID limits** ([Apple](https://developer.apple.com/support/compare-memberships/)):
  7-day profiles, a few apps and App IDs per week, and no capabilities that need a
  paid team (push notifications, associated domains / Universal Links, iCloud...).
- **Not for distribution.** No App Store / TestFlight upload; use a Mac or CI for that.
- **Verified once.** One Windows PC, one iPhone, one real app with eight native
  plugins and a SwiftPM template app. Notifications, file sharing, background modes
  and offline flows were not tested on-device.
- Native Linux (no WSL) should work for building; for USB on native Linux use the
  system `usbmuxd` instead of the Windows relay. Not tested.

## Security and privacy

- Your Apple ID password and 2FA code are entered only into `xtool auth login`.
  Don't paste them into chats, issues or logs.
- Apple Mobile Device Support listens on `127.0.0.1:27015` only; the install script
  stops it if it ever listens elsewhere. The relay socket is a UNIX socket readable
  only by your WSL user and does not log traffic.
- `prepare-flutter-ios.sh` runs build scripts from omarchy-apple-dev and Google's
  Dart toolchain (`gclient` hooks download and execute prebuilt tools). Read them
  first if that matters to you; the omarchy commit is pinned.
- Nothing here jailbreaks, wipes or reconfigures the phone beyond Developer Mode and
  trusting your own development certificate, both of which you do by hand.

## Tested configuration

| Component | Version |
| --- | --- |
| Host | Windows 11 x64, WSL 2.6, Ubuntu 24.04.5 x86_64 |
| Swift | 6.4.0 (swift.org, signature verified) |
| xtool | upstream `e3ce2c4` + #406 (the auth fixes released in 1.24.0) |
| iOS SDK | Xcode 27.0 (27A266a), iPhoneOS 27.0 |
| Flutter | 3.47.5 / Dart 3.13.4 |
| omarchy-apple-dev | `f6af7cf` + [patch](../../flutter/patches/omarchy-apple-dev-f6af7cf.patch) |
| Native libs | libplist 2.6.0, libimobiledevice-glue 1.3.1, libusbmuxd 2.1.0, libtatsu 1.0.4, libimobiledevice 1.4.0 |
| USB | Apple Mobile Device Support 20.0.0.35 + WSL relay |
| Device | iPhone (iPhone17,2), iOS 27.0.1, free Apple ID |
| Result | Flutter app built (11.8 MB IPA, 5 arm64 Mach-O), signed, installed, opened, logged in and showed live data |

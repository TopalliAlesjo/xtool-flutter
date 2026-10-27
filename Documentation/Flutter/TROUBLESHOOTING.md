# Troubleshooting

Every problem below was hit while getting the first Flutter app onto an iPhone from
WSL. Back to the [guide](GUIDE.md).

## Toolchain

### `gpg: no valid OpenPGP data found` when importing the Swift key

The key URL is served gzip-encoded. Download it with `curl --compressed`.

### xtool build fails linking with `-llzma`

`sudo apt-get install liblzma-dev`, then rebuild.

### `idevice_events_subscribe` not found / SwiftyMobileDevice build errors

Ubuntu 24.04's libimobiledevice 1.3 is too old. Run
`flutter/scripts/build-native-deps.sh` and make sure `env.sh` is sourced so
`PKG_CONFIG_PATH`/`LD_LIBRARY_PATH` point at `~/xtool-flutter-lab/native`.

### Flutter cannot determine the engine version

A shallow `git clone` of Flutter may not let the tool work out which engine
artifacts to download. Set the engine hash of your release explicitly, taken from
`bin/internal/engine.version` of an official Flutter install of the **same** version:

```bash
export FLUTTER_PREBUILT_ENGINE_VERSION=<40-char hash>
flutter --version
```

(The Linux release archive for some versions returned HTTP 404 from Google's
storage, which is why the guide clones the tag.)

### `Flutter's iOS gen_snapshot is not the Linux build`

`prepare-flutter-ios.sh` has not finished, or you switched Flutter versions. Run it
again; it skips work already done.

## Building the IPA

### Asset catalog step fails (`actool` not found or not executable)

The `actool` inside the Xcode SDK is a macOS binary. `build-ipa.sh` uses the Linux
one built by `prepare-flutter-ios.sh`; set `ACTOOL=...` if you built it elsewhere.

### Linker errors for a plugin / `no such module`

The plugin has no Swift package. See step 7 of the guide; for Objective-C-only
plugins use `flutter/scripts/swiftpm-objc-plugin-adapter.py`.

### Home-screen name shows `$(APP_DISPLAY_NAME)`

Set `APP_DISPLAY_NAME="My App"` when running `build-ipa.sh`.

### App crashes when entering/resuming a workout; small icons are distorted

Upgrade the helper with `prepare-flutter-ios.sh`, rebuild and reinstall the IPA.
The old Linux pipeline omitted Objective-C categories used by `wakelock_plus`
and wrote bitmap rows with a different stride from the catalog's metadata.
Both are fixed in the helper; replacing the original logo or suppressing Dart
errors does not fix them. See [causes, binary checks and regressions](IOS-FIXES.md).

## Apple ID login

### `Error: This action cannot be completed at this time. (-80046)`

Known xtool issue ([#378](https://github.com/xtool-org/xtool/issues/378)), fixed by
[#380](https://github.com/xtool-org/xtool/pull/380). It does **not** mean your
password is wrong. Update this repository and rebuild xtool.

### `POST https://gsa.apple.com/grandslam/GsService2 failed: HTTP 503`

Fixed upstream by [#406](https://github.com/xtool-org/xtool/pull/406) (xtool 1.24.0).
Rebuild from current sources. Don't retry many times in a row: repeated failed
logins can get the Apple ID rate-limited.

### Where do I log in?

In a WSL terminal you can see: `xtool auth login --mode password`. A login started
in a hidden or background window cannot receive your input.

## USB and the device

### `xtool install` signs the app, then hangs before uploading

This is USB/IP (`usbipd-win`): pairing and small requests work, large transfers
stall. Detach the phone from WSL and use Apple Mobile Device Support on Windows with
`flutter/windows/usbmuxd-relay.py` (guide step 8).

### `usbipd` errors about the `VBoxUSBMon` driver/service

Only relevant if you still use USB/IP. The usbipd-win driver service was missing;
a repair install of the same signed usbipd-win MSI fixed it
(`msiexec /fvamus <msi> /qn /norestart`, as administrator).

### The phone disappears from WSL after a while

WSL stops an idle distribution, which also drops USB/IP attachments. Keep a WSL
terminal open during the session. The Windows relay is not affected by this.

### Pairing stays "pending" / repeated *Trust This Computer?* prompts

Unlock the phone, keep it on the Home Screen, tap **Trust**, enter the passcode,
then retry. Each new host (Windows driver, WSL usbmuxd) pairs separately.

### `Cannot reach Apple Mobile Device Service on 127.0.0.1:27015`

The Windows service is not running or not installed. Check
`Get-Service 'Apple Mobile Device Service'` in PowerShell.

### Developer Mode is not in Settings

It only appears after the first attempt to install a development-signed app. Run
`xtool install` once, then look again under *Privacy & Security*.

### *Untrusted Developer* when opening the app

Trust your own certificate: *Settings → General → VPN & Device Management →
Apple Development: <your Apple ID> → Trust*.

### `xtool launch` returns an error

Launching through the debug server did not work in testing. Tap the app icon.

### The app stops opening after a week

Free-account profiles expire after 7 days. Rebuild if needed and run
`xtool install` again.

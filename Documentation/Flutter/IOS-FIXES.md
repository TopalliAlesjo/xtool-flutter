# Native runner and app-icon fixes — 27 October 2026

Two build defects were found in the pinned Linux Flutter/iOS toolchain while
investigating SetUp 1.0.5 build 6. Both belong to the build pipeline; SetUp's
workout state machine and original icon assets do not need a workaround.

## Runner terminates on entry or resume

`wakelock_plus` 1.8.0 calls the `UIApplication(idleTimerLock)` Objective-C
category when the runner keeps the screen awake. The old Runner linked the
plugin class but omitted the category object. Dart's `try/catch` cannot catch
the resulting native Objective-C exception.

The extra [linker patch](../../flutter/patches/omarchy-objc-linking-f6af7cf.patch)
passes `-ObjC` to the final link, retaining Objective-C categories. This is the
fix described in [Apple QA1490](https://developer.apple.com/library/archive/qa/qa1490/_index.html).
The original executable has no `UIApplication(idleTimerLock)` methods; the
rebuilt executable contains its category, `+load` and all instance methods.
Six real iPhone crash reports from build 6 were subsequently collected without
removing them from the device. Symbolication against the old Runner identifies
`-[WakelockPlusPlugin toggleMsg:error:]` followed by Objective-C
`doesNotRecognizeSelector:` and `SIGABRT`, confirming this cause.

`build-ipa.sh` now runs [verify-ios-bundle.py](../../flutter/scripts/verify-ios-bundle.py)
on the final Runner and refuses a build containing `wakelock_plus` without
its linked category. It reads the category list in the Mach-O, including chained
rebases; finding a selector string alone is insufficient. LLVM 18's Objective-C
metadata dump does not resolve these rebases, so it cannot serve as this gate.

## Distorted small app icons

AssetKit revision `705ce2f2b797835cf4bac65e0dff1e9ca37ba0bf` writes tightly
packed MLEC bitmap rows, while its CSI TVL 1007 declares a stride rounded up
to 16 bytes. An 87-pixel-wide icon contains 348 bytes per row but declares
352. CoreUI advances four extra bytes per row and shears the image. The
29, 58 and 167-pixel formats are affected too. Loose PNGs remain correct,
which is why a PNG-only check missed the problem.

[prepare-assetkit.py](../../flutter/scripts/prepare-assetkit.py) checks the pinned
upstream file's SHA-256, makes a local copy under
`tools/darwin-tools/Patched/AssetKit`, preserves its licenses and applies the
[row-padding fix](../../flutter/patches/MLECBody.swift). SwiftPM uses this local
package. The upstream checkout and shared Flutter SDK are not modified. An
unknown upstream file or a modified existing fix causes preparation to stop.

Every row, including rows in the final partial chunk and 1–2-row images, now
contains the padding declared in the CSI metadata. The fix covers 2, 4 and
8-byte pixel formats. Aligned images retain the same pixel data.

## Upgrade an existing lab

Pull these scripts, source your lab environment, then rerun preparation and
rebuild the IPA. Install over the existing app to preserve its data:

```bash
bash flutter/scripts/prepare-flutter-ios.sh
APP_DISPLAY_NAME="My App" bash flutter/scripts/build-ipa.sh /path/to/app APP_ENV=production
xtool install --usb /path/to/app/build/ios-linux/Runner.ipa
```

`OMARCHY_APPLE_DEV` optionally selects an existing pinned helper directory;
otherwise both scripts use `$XTOOL_FLUTTER_LAB/omarchy-apple-dev`.
The existing display-name/privacy patch and the new linker patch are applied
independently, so a lab with only the earlier patch can be upgraded.

## Regressions

```bash
python3 -m unittest discover -s flutter/tests -p 'test_*.py'

# After preparation, with the lab's Swift toolchain on PATH:
cd "$XTOOL_FLUTTER_LAB/omarchy-apple-dev/tools/darwin-tools/Patched/AssetKit"
swift test --filter AssetKitRowStrideTests

# Validate pixels inside the actual compiled catalog against original PNGs:
IOS_ICON_BUNDLE=/path/to/app/build/ios-linux/Payload/Runner.app \
IOS_ICON_SOURCE=/path/to/app swift test --filter CompiledIconTests

# Full upstream suite (Linux also needs librsvg2-bin):
swift test
```

Verified on 27 October 2026:

- The unmodified row encoder fails the new regression (324 issues); the fix
  passes 13 width cases × 3 pixel formats × 5 heights.
- The compiled icon test fails on the original SetUp catalog (29 issues) and
  passes on the rebuilt catalog, checking every original icon filename and
  every row's actual pixels.
- The final-bundle gate rejects the old Runner and accepts the rebuilt
  Runner, including all 19 source icon entries.
- The full AssetKit suite passes after installing its SVG rasterizer;
  Apple's `assetutil` check remains unavailable on Linux.
- SetUp's relevant Flutter suite: 220 passed; `flutter analyze`: clean.
  Relevant PHP suite: 168 passed, one skipped external-workbook fixture.
- `make lint` completes with existing warnings and no serious violations.

SetUp's replacement development IPA is 1.0.5 build 7 with the same production
bundle ID. On 27 October it was signed and installed over the existing app
with `xtool install --usb` (exit 0, installation 100%, no uninstall or reset).
The user then confirmed on the physical iPhone: **workout resumed successfully
and icon correct** in the requested Home/app-switcher check. This acceptance
covers the two reported defects; it does not extend to untested notification,
sharing or background scenarios.

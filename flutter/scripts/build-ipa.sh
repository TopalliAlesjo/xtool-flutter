#!/usr/bin/env bash
# Build an unsigned release arm64 IPA of a Flutter app on Linux.
#
#   flutter/scripts/build-ipa.sh <flutter app dir> [KEY=VALUE dart-define ...]
#
# Output: <app dir>/build/ios-linux/Runner.ipa. `xtool install` signs it with your
# Apple ID. Run prepare-flutter-ios.sh once first.
#
# Env overrides (passed through to omarchy's flutter/build.sh):
#   APP_DISPLAY_NAME  home-screen name, if Info.plist uses $(APP_DISPLAY_NAME)
#   BUNDLE_ID, BUILD_NAME, BUILD_NUMBER, MIN_IOS (defaults from the Xcode project/pubspec)
set -euo pipefail

lab=${XTOOL_FLUTTER_LAB:-$HOME/xtool-flutter-lab}
omarchy=${OMARCHY_APPLE_DEV:-$lab/omarchy-apple-dev}
app=${1:?usage: build-ipa.sh <flutter app dir> [KEY=VALUE ...]}

[ -x "$omarchy/flutter/build.sh" ] || { echo "run flutter/scripts/prepare-flutter-ios.sh first" >&2; exit 1; }
export ACTOOL=${ACTOOL:-$omarchy/tools/darwin-tools/.build/release/actool}
[ -x "$ACTOOL" ] || { echo "Linux actool not built: $ACTOOL" >&2; exit 1; }
export FLUTTER=${FLUTTER:-$(command -v flutter)}

bash "$omarchy/flutter/build.sh" "$@"
ipa=$(readlink -f "$app")/build/ios-linux/Runner.ipa
python3 "$(dirname "$(readlink -f "$0")")/verify-ios-bundle.py" \
  "$(dirname "$ipa")/Payload/Runner.app" --source "$app"
echo "IPA: $ipa"
sha256sum "$ipa"

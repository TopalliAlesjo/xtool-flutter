#!/usr/bin/env bash
# One-time (per Flutter version) preparation for building Flutter iOS apps on Linux.
#
#   flutter/scripts/prepare-flutter-ios.sh
#
# 1. Clones omarchy-apple-dev (MIT) at a pinned commit and applies this repo's patch.
# 2. Builds its Linux `actool` stand-in (asset catalogs: app icon, launch images).
# 3. Runs its flutter/setup.sh, which builds Dart's gen_snapshot for iOS on Linux
#    from the Dart revision your Flutter SDK pins (~7 GB download, long build) and
#    swaps it into the Flutter cache.
#
# Requires: env.sh sourced (swift, flutter on PATH) and `xtool sdk install` done.
set -euo pipefail

here=$(dirname "$(readlink -f "$0")")
lab=${XTOOL_FLUTTER_LAB:-$HOME/xtool-flutter-lab}
omarchy=$lab/omarchy-apple-dev
omarchy_commit=f6af7cf5e45bbc756892972d036fc49ed35ed15e
patch=$here/../patches/omarchy-apple-dev-f6af7cf.patch

command -v flutter >/dev/null || { echo "flutter is not on PATH; source env.sh" >&2; exit 1; }
command -v swift >/dev/null || { echo "swift is not on PATH; source env.sh" >&2; exit 1; }

if [ ! -d "$omarchy/.git" ]; then
  git clone -q --no-checkout https://github.com/joshuaswarren/omarchy-apple-dev.git "$omarchy"
  git -C "$omarchy" checkout -q --detach "$omarchy_commit"
fi
[ "$(git -C "$omarchy" rev-parse HEAD)" = "$omarchy_commit" ] ||
  { echo "$omarchy is not at $omarchy_commit" >&2; exit 1; }
if git -C "$omarchy" apply --check "$patch" 2>/dev/null; then
  git -C "$omarchy" apply "$patch"
  echo "== omarchy patch applied"
elif git -C "$omarchy" apply --reverse --check "$patch" 2>/dev/null; then
  echo "== omarchy patch already applied"
else
  echo "omarchy checkout has local changes that conflict with $patch" >&2; exit 1
fi

echo "== Linux actool"
(cd "$omarchy/tools/darwin-tools" &&
  swift package resolve --force-resolved-versions &&
  swift build --configuration release --product actool --disable-automatic-resolution)

echo "== Dart gen_snapshot for iOS (long)"
FLUTTER_IOS_WORK=${FLUTTER_IOS_WORK:-$lab/dart-ios} FLUTTER=$(command -v flutter) bash "$omarchy/flutter/setup.sh"

echo "Done. ACTOOL=$omarchy/tools/darwin-tools/.build/release/actool"

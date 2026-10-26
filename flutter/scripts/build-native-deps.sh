#!/usr/bin/env bash
# Build the libimobiledevice stack xtool links against, at pinned commits, into
# "$XTOOL_FLUTTER_LAB/native". No sudo, no system libraries replaced.
#
#   flutter/scripts/build-native-deps.sh
#
# Ubuntu 24.04 ships libimobiledevice 1.3, which lacks idevice_events_subscribe
# (required by SwiftyMobileDevice), so the stack is built from source.
set -euo pipefail

lab=${XTOOL_FLUTTER_LAB:-$HOME/xtool-flutter-lab}
prefix=$lab/native
sources=$lab/native-sources
mkdir -p "$prefix" "$sources"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$prefix/lib64/pkgconfig"
export LD_LIBRARY_PATH="$prefix/lib:$prefix/lib64"

# repo version commit -- order matters (each depends on the previous ones).
while read -r repo version commit; do
  dir=$sources/$repo
  if [ ! -d "$dir/.git" ]; then
    git init -q "$dir"
    git -C "$dir" fetch -q --depth 1 "https://github.com/libimobiledevice/$repo.git" "$commit"
    git -C "$dir" checkout -q --detach FETCH_HEAD
  fi
  [ "$(git -C "$dir" rev-parse HEAD)" = "$commit" ] || { echo "$repo is not at $commit" >&2; exit 1; }
  echo "== $repo $version"
  flags=()
  case "$repo" in libplist|libimobiledevice) flags+=(--without-cython) ;; esac
  (cd "$dir" &&
    RELEASE_VERSION="$version" ./autogen.sh --prefix="$prefix" --disable-static "${flags[@]}" >/dev/null &&
    make -j"$(nproc)" >/dev/null &&
    make install >/dev/null)
done <<'PINS'
libplist 2.6.0 2117b8fdb6b4096455bd2041a63e59a028120136
libimobiledevice-glue 1.3.1 a4ec1cf9cc7084cbe5571e31640ef773701e5f51
libusbmuxd 2.1.0 2387d8e5820ee4621494e20434c0017aba6bea71
libtatsu 1.0.4 ec295dd6585a900207125d41fab8535ce0c8d3dc
libimobiledevice 1.4.0 149f7623c672c1fa73122c7119a12bfc0012f2ac
PINS

for pc in libplist-2.0 libimobiledevice-glue-1.0 libusbmuxd-2.0 libtatsu-1.0 libimobiledevice-1.0; do
  printf '%s %s\n' "$pc" "$(pkg-config --modversion "$pc")"
done

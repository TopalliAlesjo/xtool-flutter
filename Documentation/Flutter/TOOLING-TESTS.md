# Pipeline maintenance and regression tests

The fork maintains the Flutter/WSL helpers and targeted CLI robustness fixes.
The native runner/category and icon-stride corrections are documented separately
in [IOS-FIXES.md](IOS-FIXES.md).

## Local checks

With the lab's Swift and native libraries on PATH, from a Linux checkout:

```bash
XTL_CI=1 swift build --product xtool
XTL_CI=1 swift test
make lint
python3 -m unittest discover -s flutter/tests -p 'test_*.py'
node --test flutter/tests/bridge.test.cjs
for script in flutter/scripts/*.sh flutter/scripts/env.sh.example; do
  bash -n "$script"
  shellcheck --severity=warning "$script"
done
```

The Swift tests use synthetic data for storage, connection pooling, prompt input,
certificate descriptions and partial USB writes. They do not log in, revoke
certificates, reset pairing or modify an installed app. `validateXcode` requires
a real Xcode bundle; it is cancelled when none is available.

SwiftLint should run on LF sources as in the Linux CI checkout. A Windows
checkout mounted through `/mnt/c` may have CRLF Swift files and produce false
whitespace warnings. The WSL shell/Python/Node scripts and sourced environment
template explicitly keep LF through `.gitattributes`; the format regression
also checks the template, whose `.sh.example` suffix needs its own rule.

`.github/workflows/flutter-tools.yml` runs the portable Python, Node and Bash
checks on pull requests and pushes to main. The existing Swift workflow builds
and tests the native library. GitHub execution and Mac/Xcode builds remain
separate from a successful local check. Release images use the current
repository's GHCR namespace rather than a hard-coded upstream repository;
see [GitHub's publishing example](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images).

## Runtime guarantees added on 27 October 2026

- Filesystem credential storage uses a private `0700` data directory, `0600`
  files and atomic replacement. Reading a legacy file tightens its permissions;
  failures other than absence are no longer silently presented as missing data.
  Deleting absent keys and clearing cached signing information are idempotent.
- AFC uploads retry only an unwritten suffix, reject zero/invalid write counts,
  use a unique staging path for each upload and remove failed partial uploads.
- Failed connection creation is removed from the single-flight pool so a
  transient error can be retried. Concurrent successful requests still share
  the same connection.
- An EOF on a console prompt fails clearly; it cannot spin through certificate
  confirmations or menu choices. Certificate descriptions tolerate the optional
  fields permitted by Apple's API without changing the confirmation requirement.
- The Objective-C adapter preserves existing YAML mappings and nested source
  paths, accepts numeric deployment versions such as `15.0`, recognizes existing
  shared `darwin` Swift packages, and rejects unsupported YAML/Swift before
  publishing a copy. It does not modify the pub cache. Generated YAML is replaced
  atomically. Resources and third-party pod dependencies still need a custom
  package.
- AssetKit preparation builds in a temporary directory and publishes the local
  package atomically, so an interrupted copy can be retried. Existing modified
  copies are preserved and rejected for review.
- The Windows bridge times out while establishing a connection, then permits
  indefinitely idle usbmux event subscriptions. The relay refuses shared or
  foreign-owned socket parents without changing their permissions, and closes
  a waiting client when Windows interop cannot launch Node.

For a custom relay socket, choose a new directory under your Linux home or an
existing directory owned by you with mode `0700`. Do not use `/tmp/name.sock`
directly: `/tmp` is shared and the relay deliberately refuses that parent.
The socket itself is `0600`; stopping the relay removes only its own socket.

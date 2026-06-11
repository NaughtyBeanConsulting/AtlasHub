#!/usr/bin/env bash
# Compile Tailwind locally with the standalone CLI (no Node/npm required).
# Re-run this whenever template markup changes so the utility set stays in sync.
#
#   ./build_tailwind.sh            # minified production build
#   ./build_tailwind.sh --watch    # rebuild on change during development
set -euo pipefail

cd "$(dirname "$0")"

TW_VERSION="v3.4.17"
TW_BIN=".tailwind/tailwindcss"

# Pick the right standalone binary for this machine.
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  TW_TARGET="macos-arm64" ;;
  Darwin-x86_64) TW_TARGET="macos-x64" ;;
  Linux-x86_64)  TW_TARGET="linux-x64" ;;
  Linux-aarch64) TW_TARGET="linux-arm64" ;;
  *) echo "Unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
esac

if [ ! -x "$TW_BIN" ]; then
  echo "Downloading Tailwind standalone CLI ${TW_VERSION} (${TW_TARGET})..."
  mkdir -p .tailwind
  curl -fsSL -o "$TW_BIN" \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/${TW_VERSION}/tailwindcss-${TW_TARGET}"
  chmod +x "$TW_BIN"
fi

EXTRA=""
if [ "${1:-}" = "--watch" ]; then EXTRA="--watch"; else EXTRA="--minify"; fi

exec "$TW_BIN" \
  -c tailwind.config.js \
  -i static/src/tailwind.css \
  -o static/css/tailwind.css \
  $EXTRA

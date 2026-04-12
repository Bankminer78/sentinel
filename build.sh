#!/usr/bin/env bash
# Build Sentinel.app — wraps the SwiftPM SentinelApp executable into a
# proper macOS .app bundle, embeds the sentinel CLI, and writes a minimal
# Info.plist with LSUIElement=true so it runs as a menu bar accessory.
set -euo pipefail
cd "$(dirname "$0")"

APP_NAME="Sentinel"
BUILD_DIR="build"
APP_DIR="$BUILD_DIR/$APP_NAME.app"
CONTENTS="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS/MacOS"
RES_DIR="$CONTENTS/Resources"

CONFIG="${CONFIG:-release}"

echo "==> swift build ($CONFIG)..."
swift build -c "$CONFIG"

echo "==> wrap into .app bundle..."
rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RES_DIR"

cp ".build/$CONFIG/SentinelApp" "$MACOS_DIR/$APP_NAME"
# Ship the sentinel CLI inside the bundle. We put it in Resources/
# rather than MacOS/ because APFS is case-insensitive — `Sentinel` and
# `sentinel` would collide in the same directory and the second copy
# would overwrite the first. The SwiftUI app reaches the CLI via
# `Bundle.main.url(forResource: "sentinel", withExtension: nil)`, and
# the user can symlink it onto $PATH separately:
#   ln -s "$PWD/build/Sentinel.app/Contents/Resources/sentinel" /usr/local/bin/
cp ".build/$CONFIG/sentinel" "$RES_DIR/sentinel"

cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Sentinel</string>
  <key>CFBundleDisplayName</key>
  <string>Sentinel</string>
  <key>CFBundleIdentifier</key>
  <string>app.sentinel</string>
  <key>CFBundleVersion</key>
  <string>0.1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleExecutable</key>
  <string>Sentinel</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
  </dict>
</dict>
</plist>
PLIST

echo
echo "Built: $APP_DIR"
echo "Run:   open $APP_DIR"

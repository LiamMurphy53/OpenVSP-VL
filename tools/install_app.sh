#!/usr/bin/env bash
# Builds the native "OpenVSP Studio.app" and installs it in ~/Applications, so Studio
# opens like any Mac app (Spotlight, Launchpad, Dock) in its own window, not a browser.
# The app runs this checkout; rerun after moving the project folder.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
app="${1:-$HOME/Applications/OpenVSP Studio.app}"
build="$(mktemp -d)"
trap 'rm -rf "$build"' EXIT

swiftc -O -o "$build/OpenVSPStudio" "$root/macos/StudioApp.swift" -framework AppKit -framework WebKit
swift "$root/macos/make_icon.swift" "$build/icon.iconset"
iconutil -c icns -o "$build/icon.icns" "$build/icon.iconset"

rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$build/OpenVSPStudio" "$app/Contents/MacOS/OpenVSPStudio"
cp "$build/icon.icns" "$app/Contents/Resources/icon.icns"
cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>OpenVSP Studio</string>
  <key>CFBundleDisplayName</key><string>OpenVSP Studio</string>
  <key>CFBundleIdentifier</key><string>local.openvsp.studio</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>OpenVSPStudio</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.developer-tools</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>StudioRoot</key><string>$root</string>
</dict>
</plist>
PLIST
codesign --force --sign - "$app" >/dev/null
touch "$app"
echo "Installed: $app"

// SentinelApp entry point.
//
// We use the imperative AppKit bootstrap (NSApplication.shared.run())
// instead of @main + SwiftUI App because:
//   - It gives the AppDelegate full control over the menu bar status item,
//     window lifecycle, and accessory activation policy.
//   - SwiftUI's WindowGroup/Window scenes auto-open windows on launch,
//     which is wrong for a menu bar app — we want zero windows until the
//     user clicks the 🛡 in the menu bar.
//   - main.swift + top-level statements is what SwiftPM executable
//     targets prefer; @main on a struct works but adds friction.
//
// The window itself is a SwiftUI ContentView hosted in an NSHostingView,
// so all the application UI is still SwiftUI — just managed imperatively
// by the AppDelegate.

import AppKit

let delegate = AppDelegate()
let app = NSApplication.shared
app.delegate = delegate
app.setActivationPolicy(.accessory)
app.run()

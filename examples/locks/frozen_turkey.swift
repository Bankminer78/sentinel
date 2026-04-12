#!/usr/bin/env swift
// sentinel: name="Frozen Turkey"
// sentinel: description="60-second total screen lockout. Spawns a black NSWindow on every monitor at .screenSaver level. Survives Cmd+Tab and force-quit until the timer expires."

// This example shows that "lock as script" can include a real native UI
// when you want it to. Run it with `swift frozen_turkey.swift` and the
// JIT compiles it on the fly. The Sentinel app does the same thing when
// you click Run on this lock — the language is "swift" and the spawn
// path is `/usr/bin/env swift <file>`.

import Cocoa

let DURATION: TimeInterval = 60

NSApplication.shared.setActivationPolicy(.regular)

NSApp.presentationOptions = [
    .hideDock,
    .hideMenuBar,
    .disableAppleMenu,
    .disableProcessSwitching,
    .disableForceQuit,
    .disableSessionTermination,
    .disableHideApplication,
]

let end = Date().addingTimeInterval(DURATION)
var windows: [NSWindow] = []
var labels: [NSTextField] = []

for screen in NSScreen.screens {
    let win = NSWindow(
        contentRect: screen.frame,
        styleMask: [.borderless],
        backing: .buffered,
        defer: false)
    win.level = .screenSaver
    win.collectionBehavior = [.canJoinAllSpaces, .stationary, .fullScreenAuxiliary]
    win.backgroundColor = .black
    win.isOpaque = true
    win.hasShadow = false
    win.ignoresMouseEvents = false

    let label = NSTextField(labelWithString: "")
    label.font = .monospacedDigitSystemFont(ofSize: 96, weight: .ultraLight)
    label.textColor = .white
    label.alignment = .center
    label.backgroundColor = .clear
    label.isBordered = false
    label.frame = NSRect(
        x: 0,
        y: screen.frame.height / 2 - 60,
        width: screen.frame.width,
        height: 120)
    label.autoresizingMask = [.minXMargin, .maxXMargin, .minYMargin, .maxYMargin]

    let hint = NSTextField(labelWithString: "Frozen until the timer ends.")
    hint.font = .systemFont(ofSize: 14, weight: .regular)
    hint.textColor = NSColor.white.withAlphaComponent(0.4)
    hint.alignment = .center
    hint.backgroundColor = .clear
    hint.isBordered = false
    hint.frame = NSRect(
        x: 0,
        y: screen.frame.height / 2 - 110,
        width: screen.frame.width,
        height: 30)
    hint.autoresizingMask = [.minXMargin, .maxXMargin, .minYMargin, .maxYMargin]

    win.contentView?.addSubview(label)
    win.contentView?.addSubview(hint)
    win.makeKeyAndOrderFront(nil)
    windows.append(win)
    labels.append(label)
}

NSApp.activate(ignoringOtherApps: true)

func tick() {
    let left = max(0, Int(end.timeIntervalSinceNow))
    let m = String(format: "%02d", left / 60)
    let s = String(format: "%02d", left % 60)
    for label in labels {
        label.stringValue = "\(m):\(s)"
    }
    if left <= 0 {
        for w in windows { w.orderOut(nil) }
        NSApp.terminate(nil)
    }
}

tick()
Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in tick() }
NSApp.run()
